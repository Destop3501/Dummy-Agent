import json
import re
from typing import Any, Callable, Dict, List, Optional
from agent_observability.phase1_agent_host.models import ToolSchema, ToolParameter
from agent_observability.phase2_tracing.models import ExecutionTraceSpan, SpanStatus, SpanType
from agent_observability.phase3_observer.models import EvaluationVerdict, FailureCategory


def _check_type(val: Any, expected_type_str: str) -> bool:
    """Check if value matches the expected type string."""
    t = expected_type_str.lower()
    if t in ("string", "str"):
        return isinstance(val, str)
    elif t in ("integer", "int"):
        return isinstance(val, int) and not isinstance(val, bool)
    elif t in ("float", "number"):
        return isinstance(val, (int, float)) and not isinstance(val, bool)
    elif t in ("boolean", "bool"):
        return isinstance(val, bool)
    elif t in ("object", "dict"):
        return isinstance(val, dict)
    elif t in ("array", "list"):
        return isinstance(val, list)
    return True


class EvaluationNode:
    """
    Observer node that continuously ingests execution traces to evaluate execution state.
    Compares trace inputs & outputs against tool schemas and expected data formats,
    detecting missing parameters, syntax errors, or API rejections, and routes failed
    traces to the recovery module.
    """

    def __init__(
        self,
        tool_schemas: Optional[Dict[str, ToolSchema]] = None,
        recovery_router: Optional[Callable[[EvaluationVerdict, ExecutionTraceSpan], Any]] = None,
    ):
        self.tool_schemas: Dict[str, ToolSchema] = dict(tool_schemas or {})
        self.recovery_router = recovery_router
        self.evaluations_history: List[EvaluationVerdict] = []
        self.failed_queue: List[EvaluationVerdict] = []

    def register_tool_schema(self, schema: ToolSchema) -> None:
        """Register a tool schema for validation."""
        self.tool_schemas[schema.name] = schema

    def set_recovery_router(
        self, router: Callable[[EvaluationVerdict, ExecutionTraceSpan], Any]
    ) -> None:
        """Set the routing callback for failed traces."""
        self.recovery_router = router

    def ingest_trace(self, span: ExecutionTraceSpan) -> EvaluationVerdict:
        """
        Evaluate an incoming trace span against registered schemas and runtime integrity rules.
        If a failure is detected, routes the failed trace to the recovery module.
        """
        verdict = self._evaluate_span(span)
        self.evaluations_history.append(verdict)

        if not verdict.is_valid:
            self.failed_queue.append(verdict)
            if self.recovery_router:
                self.recovery_router(verdict, span)

        return verdict

    def _evaluate_span(self, span: ExecutionTraceSpan) -> EvaluationVerdict:
        """Perform deep evaluation of a single trace span."""
        # Non-tool spans (e.g. general prompt) with explicit failure
        if span.span_type != SpanType.TOOL:
            if span.status == SpanStatus.FAILED or span.error is not None:
                err_msg = span.error.message if span.error else "Unknown execution failure"
                return EvaluationVerdict(
                    is_valid=False,
                    failure_category=FailureCategory.RUNTIME_EXCEPTION,
                    diagnostic_message=f"Prompt/Workflow failed: {err_msg}",
                    deviations=[err_msg],
                    span_id=span.span_id,
                    trace_id=span.trace_id,
                    tool_inputs=span.inputs,
                )
            return EvaluationVerdict(
                is_valid=True,
                diagnostic_message="Prompt span passed validation.",
                span_id=span.span_id,
                trace_id=span.trace_id,
                tool_inputs=span.inputs,
            )

        # Tool execution span evaluation
        tool_name = span.name
        schema = self.tool_schemas.get(tool_name)
        deviations: List[str] = []

        # 1. Check for caught runtime exceptions or API rejections
        if span.status == SpanStatus.FAILED or span.error is not None:
            err = span.error
            err_msg = err.message.lower() if err else ""
            err_type = err.error_type if err else ""

            # Detect API rejections (HTTP 4xx, 5xx, connection refused, unauthorized)
            api_keywords = ["404", "500", "403", "401", "400", "http", "api", "connection refused", "timeout", "rejected"]
            if any(k in err_msg for k in api_keywords) or "HTTPError" in err_type:
                return EvaluationVerdict(
                    is_valid=False,
                    failure_category=FailureCategory.API_REJECTION,
                    diagnostic_message=f"API Rejection detected in tool '{tool_name}': {err.message if err else ''}",
                    deviations=[err.message if err else "API Rejection"],
                    span_id=span.span_id,
                    trace_id=span.trace_id,
                    tool_name=tool_name,
                    tool_inputs=span.inputs,
                    tool_schema=schema,
                )

            # Detect syntax or unparsed template errors
            has_template_in_inputs = any(
                isinstance(v, str) and re.search(r"\{\{.*\}\}", v)
                for v in span.inputs.values()
            )
            if has_template_in_inputs or "syntax" in err_msg or "template" in err_msg:
                return EvaluationVerdict(
                    is_valid=False,
                    failure_category=FailureCategory.SYNTAX_ERROR,
                    diagnostic_message=f"Syntax/template error detected in tool '{tool_name}': {err.message if err else ''}",
                    deviations=[err.message if err else "Syntax error", "Unparsed template expression"],
                    span_id=span.span_id,
                    trace_id=span.trace_id,
                    tool_name=tool_name,
                    tool_inputs=span.inputs,
                    tool_schema=schema,
                )

            # Detect missing parameter errors embedded in runtime errors
            if "missing" in err_msg and ("parameter" in err_msg or "argument" in err_msg):
                return EvaluationVerdict(
                    is_valid=False,
                    failure_category=FailureCategory.MISSING_PARAMETERS,
                    diagnostic_message=f"Missing parameter in tool '{tool_name}': {err.message if err else ''}",
                    deviations=[err.message if err else "Missing parameter"],
                    span_id=span.span_id,
                    trace_id=span.trace_id,
                    tool_name=tool_name,
                    tool_inputs=span.inputs,
                    tool_schema=schema,
                )

            # Detect type mismatch errors in runtime errors
            if "TypeError" in err_type or "must be" in err_msg:
                return EvaluationVerdict(
                    is_valid=False,
                    failure_category=FailureCategory.TYPE_MISMATCH,
                    diagnostic_message=f"Type mismatch detected in tool '{tool_name}': {err.message if err else ''}",
                    deviations=[err.message if err else "Type mismatch"],
                    span_id=span.span_id,
                    trace_id=span.trace_id,
                    tool_name=tool_name,
                    tool_inputs=span.inputs,
                    tool_schema=schema,
                )

            return EvaluationVerdict(
                is_valid=False,
                failure_category=FailureCategory.RUNTIME_EXCEPTION,
                diagnostic_message=f"Runtime exception in tool '{tool_name}': {err.message if err else ''}",
                deviations=[err.message if err else "Runtime exception"],
                span_id=span.span_id,
                trace_id=span.trace_id,
                tool_name=tool_name,
                tool_inputs=span.inputs,
                tool_schema=schema,
            )

        # 2. Schema Input Evaluation (Missing parameters, type mismatches, syntax errors)
        if schema:
            # Check required parameters
            required_params = schema.get_required_param_names()
            missing = [p for p in required_params if p not in span.inputs or span.inputs[p] is None]
            if missing:
                return EvaluationVerdict(
                    is_valid=False,
                    failure_category=FailureCategory.MISSING_PARAMETERS,
                    diagnostic_message=f"Tool '{tool_name}' missing required parameters: {missing}",
                    deviations=[f"Missing required parameter: {p}" for p in missing],
                    span_id=span.span_id,
                    trace_id=span.trace_id,
                    tool_name=tool_name,
                    tool_inputs=span.inputs,
                    tool_schema=schema,
                )

            # Check parameter types and syntax
            for param in schema.parameters:
                if param.name in span.inputs and span.inputs[param.name] is not None:
                    val = span.inputs[param.name]
                    # Check type compliance
                    if not _check_type(val, param.type):
                        deviations.append(
                            f"Parameter '{param.name}' expected type '{param.type}', received '{type(val).__name__}' ({val})"
                        )

                    # Check for unparsed mustache/template syntax or malformed JSON
                    if isinstance(val, str):
                        if re.search(r"\{\{.*\}\}", val):
                            deviations.append(
                                f"Parameter '{param.name}' contains unparsed template syntax: '{val}'"
                            )

            if deviations:
                # If template syntax error found
                if any("unparsed template" in d for d in deviations):
                    cat = FailureCategory.SYNTAX_ERROR
                else:
                    cat = FailureCategory.TYPE_MISMATCH

                return EvaluationVerdict(
                    is_valid=False,
                    failure_category=cat,
                    diagnostic_message=f"Schema validation failure on tool '{tool_name}': {'; '.join(deviations)}",
                    deviations=deviations,
                    span_id=span.span_id,
                    trace_id=span.trace_id,
                    tool_name=tool_name,
                    tool_inputs=span.inputs,
                    tool_schema=schema,
                )

        # 3. Output payload evaluation (check for returned error status dicts, e.g. {"status": 404})
        if isinstance(span.outputs, dict):
            status_code = span.outputs.get("status") or span.outputs.get("status_code") or span.outputs.get("statusCode")
            if status_code and isinstance(status_code, int) and status_code >= 400:
                return EvaluationVerdict(
                    is_valid=False,
                    failure_category=FailureCategory.API_REJECTION,
                    diagnostic_message=f"Tool '{tool_name}' returned HTTP error code {status_code} in output payload.",
                    deviations=[f"HTTP {status_code} returned: {span.outputs.get('error', span.outputs.get('message', ''))}"],
                    span_id=span.span_id,
                    trace_id=span.trace_id,
                    tool_name=tool_name,
                    tool_inputs=span.inputs,
                    tool_schema=schema,
                )

        # Check output format conformance against expected_output_type
        if schema and schema.expected_output_type and span.outputs is not None:
            if not _check_type(span.outputs, schema.expected_output_type):
                return EvaluationVerdict(
                    is_valid=False,
                    failure_category=FailureCategory.FORMAT_MISMATCH,
                    diagnostic_message=(
                        f"Tool '{tool_name}' returned output type '{type(span.outputs).__name__}', "
                        f"expected '{schema.expected_output_type}'"
                    ),
                    deviations=[f"Expected return format '{schema.expected_output_type}', got '{type(span.outputs).__name__}'"],
                    span_id=span.span_id,
                    trace_id=span.trace_id,
                    tool_name=tool_name,
                    tool_inputs=span.inputs,
                    tool_schema=schema,
                )

        return EvaluationVerdict(
            is_valid=True,
            diagnostic_message=f"Tool '{tool_name}' executed cleanly and satisfies schema.",
            span_id=span.span_id,
            trace_id=span.trace_id,
            tool_name=tool_name,
            tool_inputs=span.inputs,
            tool_schema=schema,
        )
