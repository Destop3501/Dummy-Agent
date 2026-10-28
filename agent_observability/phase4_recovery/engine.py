import logging
from typing import Any, Callable, Dict, List, Optional
from agent_observability.phase1_agent_host.models import ToolSchema
from agent_observability.phase2_tracing.models import ExecutionTraceSpan, SpanStatus, SpanType
from agent_observability.phase3_observer.models import EvaluationVerdict
from agent_observability.phase4_recovery.critic import CriticFunction
from agent_observability.phase4_recovery.models import (
    CriticDiagnosis,
    RecoveryResult,
    RecoveryStrategyType,
)

logger = logging.getLogger("agent_observability.recovery")


class SelfHealingRecoveryEngine:
    """
    Automated diagnostic loop that activates when the observer flags an error trace.
    Passes the failed trace to the Critic, obtains corrected context, and reinjects it
    into the primary agent/tool runtime to retry without human intervention.
    """

    def __init__(
        self,
        critic: Optional[CriticFunction] = None,
        tool_executor: Optional[Callable[[str, Dict[str, Any]], Any]] = None,
        max_retries: int = 3,
    ):
        self.critic = critic or CriticFunction()
        self.tool_executor = tool_executor
        self.max_retries = max_retries
        self.recovery_history: List[RecoveryResult] = []

    def handle_failed_trace(
        self,
        verdict: EvaluationVerdict,
        span: ExecutionTraceSpan,
        custom_executor: Optional[Callable[[str, Dict[str, Any]], Any]] = None,
    ) -> RecoveryResult:
        """
        Trigger the diagnostic loop:
        1. Pass failed trace data (input, schema, exact error payload) to Critic.
        2. Analyze root cause and generate corrected parameters.
        3. Automatically inject Critic's corrected context to retry failed tool call.
        """
        schema = verdict.tool_schema
        tool_name = verdict.tool_name or span.name
        executor = custom_executor or self.tool_executor

        # 1. Critic diagnosis
        diagnosis = self.critic.analyze(span=span, schema=schema, verdict=verdict)
        logger.info(
            f"[Self-Healing] Diagnosed tool '{tool_name}' failure. Strategy: {diagnosis.strategy}. "
            f"Root cause: {diagnosis.root_cause}"
        )

        if not executor:
            res = RecoveryResult(
                success=False,
                original_span_id=span.span_id,
                trace_id=span.trace_id,
                tool_name=tool_name,
                retry_count=0,
                diagnosis=diagnosis,
                error_message="No tool executor provided to re-execute tool.",
            )
            self.recovery_history.append(res)
            return res

        # 2. Automated retry loop with Critic's corrected context injection
        retry_count = 0
        last_error = None
        current_inputs = dict(diagnosis.corrected_inputs)

        while retry_count < self.max_retries:
            retry_count += 1
            try:
                # Inject corrected parameters into tool execution without human intervention
                recovered_output = executor(tool_name, current_inputs)

                # Mark trace span as successfully recovered
                span.status = SpanStatus.RECOVERED
                span.outputs = recovered_output
                span.metadata["recovered_by"] = "CriticSelfHealingEngine"
                span.metadata["critic_diagnosis"] = diagnosis.model_dump()
                span.metadata["retries_taken"] = retry_count

                result = RecoveryResult(
                    success=True,
                    original_span_id=span.span_id,
                    trace_id=span.trace_id,
                    tool_name=tool_name,
                    retry_count=retry_count,
                    diagnosis=diagnosis,
                    recovered_output=recovered_output,
                )
                self.recovery_history.append(result)
                logger.info(f"[Self-Healing] Tool '{tool_name}' recovered successfully after {retry_count} attempt(s).")
                return result

            except Exception as retry_err:
                last_error = str(retry_err)
                logger.warning(f"[Self-Healing] Retry {retry_count} for '{tool_name}' failed: {retry_err}")
                # Update inputs with secondary fallback if needed
                span.finish_failure(retry_err)

        # If retries exhausted
        result = RecoveryResult(
            success=False,
            original_span_id=span.span_id,
            trace_id=span.trace_id,
            tool_name=tool_name,
            retry_count=retry_count,
            diagnosis=diagnosis,
            error_message=f"Exhausted {self.max_retries} retries. Last error: {last_error}",
        )
        self.recovery_history.append(result)
        return result
