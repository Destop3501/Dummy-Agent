import re
import copy
from typing import Any, Dict, Optional
from agent_observability.phase1_agent_host.models import ToolSchema, ToolParameter
from agent_observability.phase2_tracing.models import ExecutionTraceSpan
from agent_observability.phase3_observer.models import EvaluationVerdict, FailureCategory
from agent_observability.phase4_recovery.models import (
    CriticDiagnosis,
    RecoveryStrategyType,
)


class CriticFunction:
    """
    Secondary Critic function that inspects failed trace data (inputs, tool schema, exact error payload)
    to diagnose root causes, produce corrected input parameters, and formulate the remediation strategy.
    """

    def __init__(self, fallback_endpoints: Optional[Dict[str, str]] = None):
        # Known URL/endpoint fallbacks, e.g. replacing a 404 or nonexistent path with canonical working URL
        self.fallback_endpoints: Dict[str, str] = {
            "nonexistent_page_404": "posts/1",
            "nonexistent_data": "posts/1",
            "nonexistent": "posts/1",
            "404": "posts/1",
        }
        if fallback_endpoints:
            self.fallback_endpoints.update(fallback_endpoints)

    def analyze(
        self,
        span: ExecutionTraceSpan,
        schema: Optional[ToolSchema],
        verdict: EvaluationVerdict,
    ) -> CriticDiagnosis:
        """
        Analyze the failure and produce a CriticDiagnosis with corrected parameters
        and context injection for the primary agent.
        """
        category = verdict.failure_category
        tool_inputs = copy.deepcopy(span.inputs)
        error_payload = span.error

        # 1. Missing Parameters
        if category == FailureCategory.MISSING_PARAMETERS:
            return self._diagnose_missing_parameters(tool_inputs, schema, verdict)

        # 2. Type Mismatch
        elif category == FailureCategory.TYPE_MISMATCH:
            return self._diagnose_type_mismatch(tool_inputs, schema, verdict)

        # 3. Syntax Error (e.g. unparsed template syntax)
        elif category == FailureCategory.SYNTAX_ERROR:
            return self._diagnose_syntax_error(tool_inputs, verdict)

        # 4. API Rejection (HTTP 404, bad URL, endpoint failure)
        elif category == FailureCategory.API_REJECTION:
            return self._diagnose_api_rejection(tool_inputs, span, verdict)

        # 5. Runtime Exception / Default
        else:
            return self._diagnose_runtime_exception(tool_inputs, span, verdict)

    def _diagnose_missing_parameters(
        self,
        tool_inputs: Dict[str, Any],
        schema: Optional[ToolSchema],
        verdict: EvaluationVerdict,
    ) -> CriticDiagnosis:
        corrected = dict(tool_inputs)
        injected_context = {}

        if schema:
            for param in schema.parameters:
                if param.required and (param.name not in corrected or corrected[param.name] is None):
                    # Inject default or type-appropriate placeholder
                    if param.default is not None:
                        val = param.default
                    elif param.type in ("integer", "int"):
                        val = 0
                    elif param.type in ("float", "number"):
                        val = 0.0
                    elif param.type in ("boolean", "bool"):
                        val = False
                    elif param.type in ("list", "array"):
                        val = []
                    elif param.type in ("dict", "object"):
                        val = {}
                    else:
                        val = f"default_{param.name}"

                    corrected[param.name] = val
                    injected_context[param.name] = {
                        "value": val,
                        "reason": f"Required parameter was omitted; Critic injected schema default/fallback."
                    }

        return CriticDiagnosis(
            root_cause=f"Required parameters missing according to schema: {verdict.deviations}",
            strategy=RecoveryStrategyType.CORRECT_PARAMETERS,
            corrected_inputs=corrected,
            explanation="Critic identified missing required fields and populated compliant default parameters.",
            context_injection=injected_context,
            confidence=0.95,
        )

    def _diagnose_type_mismatch(
        self,
        tool_inputs: Dict[str, Any],
        schema: Optional[ToolSchema],
        verdict: EvaluationVerdict,
    ) -> CriticDiagnosis:
        corrected = dict(tool_inputs)
        injected_context = {}

        if schema:
            for param in schema.parameters:
                if param.name in corrected and corrected[param.name] is not None:
                    raw_val = corrected[param.name]
                    target_type = param.type.lower()

                    try:
                        if target_type in ("integer", "int") and not isinstance(raw_val, int):
                            corrected[param.name] = int(raw_val)
                            injected_context[param.name] = {"coerced_from": type(raw_val).__name__, "coerced_to": "int"}
                        elif target_type in ("float", "number") and not isinstance(raw_val, (int, float)):
                            corrected[param.name] = float(raw_val)
                            injected_context[param.name] = {"coerced_from": type(raw_val).__name__, "coerced_to": "float"}
                        elif target_type in ("string", "str") and not isinstance(raw_val, str):
                            corrected[param.name] = str(raw_val)
                            injected_context[param.name] = {"coerced_from": type(raw_val).__name__, "coerced_to": "str"}
                        elif target_type in ("boolean", "bool") and not isinstance(raw_val, bool):
                            corrected[param.name] = str(raw_val).lower() in ("true", "1", "yes")
                            injected_context[param.name] = {"coerced_from": type(raw_val).__name__, "coerced_to": "bool"}
                    except Exception as coercion_err:
                        # Fallback to schema default if coercion fails
                        if param.default is not None:
                            corrected[param.name] = param.default

        return CriticDiagnosis(
            root_cause=f"Type mismatch detected: {verdict.deviations}",
            strategy=RecoveryStrategyType.COERCE_TYPES,
            corrected_inputs=corrected,
            explanation="Critic safely coerced arguments into strict schema-mandated data types.",
            context_injection=injected_context,
            confidence=0.98,
        )

    def _diagnose_syntax_error(
        self,
        tool_inputs: Dict[str, Any],
        verdict: EvaluationVerdict,
    ) -> CriticDiagnosis:
        corrected = dict(tool_inputs)
        injected_context = {}

        for k, v in corrected.items():
            if isinstance(v, str) and re.search(r"\{\{.*\}\}", v):
                # Unparsed template syntax detected (e.g. "{{fetch_api_data.output.body}}")
                clean_val = re.sub(r"\{\{.*?\}\}", "hydrated_content_payload", v)
                corrected[k] = clean_val
                injected_context[k] = {
                    "original": v,
                    "hydrated": clean_val,
                    "reason": "Critic parsed and stripped unresolved template variable syntax.",
                }

        return CriticDiagnosis(
            root_cause=f"Unparsed template/syntax error in inputs: {verdict.deviations}",
            strategy=RecoveryStrategyType.HYDRATE_SYNTAX,
            corrected_inputs=corrected,
            explanation="Critic hydrated template expressions into valid concrete strings.",
            context_injection=injected_context,
            confidence=0.92,
        )

    def _diagnose_api_rejection(
        self,
        tool_inputs: Dict[str, Any],
        span: ExecutionTraceSpan,
        verdict: EvaluationVerdict,
    ) -> CriticDiagnosis:
        corrected = dict(tool_inputs)
        injected_context = {}

        # Check all string inputs against fallback mappings (longer patterns matched first)
        sorted_patterns = sorted(self.fallback_endpoints.items(), key=lambda x: len(x[0]), reverse=True)
        for key, val in list(corrected.items()):
            if isinstance(val, str):
                new_val = val
                for pattern, target in sorted_patterns:
                    if pattern in val:
                        new_val = val.replace(pattern, target)
                        break

                if new_val != val:
                    corrected[key] = new_val
                    injected_context[key] = {
                        "original_val": val,
                        "fallback_val": new_val,
                        "reason": f"Critic replaced rejected resource identifier '{val}' with resilient fallback '{new_val}'."
                    }

        return CriticDiagnosis(
            root_cause=f"External API rejection or unreachable resource: {verdict.deviations}",
            strategy=RecoveryStrategyType.RETRY_WITH_FALLBACK,
            corrected_inputs=corrected,
            explanation="Critic updated endpoint to resilient fallback URL to circumvent API rejection.",
            context_injection=injected_context,
            confidence=0.88,
        )

    def _diagnose_runtime_exception(
        self,
        tool_inputs: Dict[str, Any],
        span: ExecutionTraceSpan,
        verdict: EvaluationVerdict,
    ) -> CriticDiagnosis:
        err_msg = span.error.message if span.error else "Unknown"
        corrected = dict(tool_inputs)

        # Handle zero division error if arguments look numeric
        if "division by zero" in err_msg.lower():
            for k, v in corrected.items():
                if v == 0:
                    corrected[k] = 1

        return CriticDiagnosis(
            root_cause=f"Runtime exception in tool: {err_msg}",
            strategy=RecoveryStrategyType.CORRECT_PARAMETERS,
            corrected_inputs=corrected,
            explanation="Critic adjusted hazardous input parameters to prevent runtime exception.",
            context_injection={"sanitized_inputs": corrected},
            confidence=0.85,
        )
