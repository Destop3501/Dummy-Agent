from typing import Any, Dict, List, Optional, Tuple
from self_healing.observer import HealthObserver, ObservationEvent
from self_healing.analyzer import DiagnosticAnalyzer
from self_healing.telemetry import create_observation_span, create_remediation_span
from self_healing.strategies.template_hydrator import TemplateHydratorStrategy
from self_healing.strategies.api_fallback import ApiFallbackStrategy
from self_healing.strategies.loop_breaker import LoopBreakerStrategy
from self_healing.strategies.entity_resolver import EntityResolverStrategy
from self_healing.strategies.json_repair import JsonRepairStrategy


class RemediationExecutor:
    """
    Coordinates the closed-loop self-healing cycle:
    Observes -> Diagnoses -> Remediates -> Records Phoenix Telemetry.
    """

    def __init__(self, observer: HealthObserver):
        self.observer = observer

    def heal_arguments(
        self,
        event: ObservationEvent,
        conversation_history: List[Dict[str, Any]],
    ) -> Tuple[bool, Dict[str, Any], str]:
        """
        Attempts self-healing remediation on invalid or hallucinated arguments.
        """
        # 1. Observation Span
        obs_span = create_observation_span(event.error_mode or "ArgumentError", event.details)
        obs_span.end()

        # 2. Diagnosis & Strategy Selection
        strategy_cls, root_cause, notes = DiagnosticAnalyzer.diagnose_and_select(event)
        if not strategy_cls:
            return False, {}, "No suitable remediation strategy found."

        # 3. Execute Strategy
        success = False
        repaired_dict = {}
        repair_notes = ""

        if strategy_cls == TemplateHydratorStrategy:
            success, repaired_dict, repair_notes = TemplateHydratorStrategy.heal(
                event.raw_input or "", conversation_history
            )
        elif strategy_cls == JsonRepairStrategy:
            success, repaired_dict, repair_notes = JsonRepairStrategy.heal(
                event.raw_input or ""
            )

        # 4. Remediation Span
        rem_span = create_remediation_span(
            strategy_name=strategy_cls.name,
            input_state=event.raw_input,
            output_state=repaired_dict,
            success=success,
            notes=repair_notes,
        )
        rem_span.end()

        return success, repaired_dict, repair_notes

    def heal_tool_execution(
        self,
        event: ObservationEvent,
    ) -> Tuple[bool, str, str]:
        """
        Attempts self-healing remediation when a tool returns an error output or raises an exception.
        """
        # 1. Observation Span
        obs_span = create_observation_span(event.error_mode or "ToolExecutionError", event.details)
        obs_span.end()

        # 2. Diagnosis & Strategy Selection
        strategy_cls, root_cause, notes = DiagnosticAnalyzer.diagnose_and_select(event)
        if not strategy_cls:
            return False, event.output_content or "Error", "No remediation strategy available."

        # 3. Execute Strategy
        success = False
        healed_output = ""
        repair_notes = ""

        if strategy_cls == ApiFallbackStrategy:
            failed_url = (event.parsed_input or {}).get("url", "")
            success, healed_output, repair_notes = ApiFallbackStrategy.heal(failed_url)

        elif strategy_cls == EntityResolverStrategy:
            entity = (event.parsed_input or {}).get("city", "unknown")
            success, healed_output, repair_notes = EntityResolverStrategy.heal(entity)

        # 4. Remediation Span
        rem_span = create_remediation_span(
            strategy_name=strategy_cls.name,
            input_state=event.output_content,
            output_state=healed_output,
            success=success,
            notes=repair_notes,
        )
        rem_span.end()

        return success, healed_output, repair_notes

    def heal_loop_stagnation(
        self,
        event: ObservationEvent,
    ) -> Tuple[bool, Dict[str, str], str]:
        """
        Intervenes when a repetition loop is detected, generating an advisory prompt.
        """
        obs_span = create_observation_span(event.error_mode or "InfiniteLoopRisk", event.details)
        obs_span.end()

        strategy_cls, root_cause, notes = DiagnosticAnalyzer.diagnose_and_select(event)

        stagnant_tool = event.details.get("stagnant_tool", "")
        parsed_args = event.parsed_input or {}
        repeated_output = event.details.get("repeated_output", "")
        turn_count = event.details.get("step_count", 0)

        success, intervention_msg, repair_notes = LoopBreakerStrategy.generate_intervention(
            stagnant_tool, parsed_args, repeated_output, turn_count
        )

        rem_span = create_remediation_span(
            strategy_name=LoopBreakerStrategy.name,
            input_state=f"Step {turn_count} loop detected",
            output_state=intervention_msg.get("content", ""),
            success=success,
            notes=repair_notes,
        )
        rem_span.end()

        return success, intervention_msg, repair_notes
