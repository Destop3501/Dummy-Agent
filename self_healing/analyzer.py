from typing import Any, Dict, Optional, Tuple
from self_healing.observer import ObservationEvent
from self_healing.telemetry import create_analysis_span
from self_healing.strategies.template_hydrator import TemplateHydratorStrategy
from self_healing.strategies.api_fallback import ApiFallbackStrategy
from self_healing.strategies.loop_breaker import LoopBreakerStrategy
from self_healing.strategies.entity_resolver import EntityResolverStrategy
from self_healing.strategies.json_repair import JsonRepairStrategy


class DiagnosticAnalyzer:
    """
    Analyzes observation anomalies, identifies root causes, selects the optimal
    healing strategy, and emits Arize Phoenix analysis spans.
    """

    STRATEGIES = [
        TemplateHydratorStrategy,
        ApiFallbackStrategy,
        LoopBreakerStrategy,
        EntityResolverStrategy,
        JsonRepairStrategy,
    ]

    @classmethod
    def diagnose_and_select(cls, event: ObservationEvent) -> Tuple[Optional[type], str, str]:
        """
        Evaluates the observation event and returns:
        (SelectedStrategyClass, RootCauseDiagnosis, DiagnosticNotes)
        """
        error_mode = event.error_mode or "UnknownError"
        details = event.details

        root_cause = "Unknown anomaly"
        notes = ""
        selected_strategy = None

        if error_mode == "SilentValidationError":
            root_cause = "LLM generated unparsed mustache/placeholder template syntax instead of evaluated variable."
            notes = f"Detected placeholders: {details.get('placeholders')}. Targeting TemplateHydrationStrategy."
            selected_strategy = TemplateHydratorStrategy

        elif error_mode == "FormatError":
            root_cause = "LLM produced malformed JSON in tool call arguments."
            notes = f"JSON Error: {details.get('json_error')}. Targeting JsonRepairStrategy."
            selected_strategy = JsonRepairStrategy

        elif "404" in error_mode or (error_mode == "ToolExecutionError" and "404" in str(event.output_content)):
            root_cause = "Target REST API endpoint does not exist (HTTP 404 Not Found)."
            notes = f"URL failed with 404. Targeting ApiFallbackStrategy."
            selected_strategy = ApiFallbackStrategy

        elif error_mode == "UnknownEntityError" or "unknown city" in str(event.output_content).lower():
            root_cause = "Queried domain entity is missing from the operational catalog."
            notes = f"Entity '{event.parsed_input.get('city') if event.parsed_input else 'unknown'}' not recognized. Targeting EntityResolverStrategy."
            selected_strategy = EntityResolverStrategy

        elif error_mode in ("InfiniteLoopRisk", "InfiniteLoopError"):
            root_cause = "Agent is stuck in an invariant polling cycle where the tool output never changes."
            notes = f"Tool '{details.get('stagnant_tool')}' repeated {details.get('repeat_count')} times. Targeting LoopBreakerStrategy."
            selected_strategy = LoopBreakerStrategy

        else:
            # Fallback strategy search
            for strat in cls.STRATEGIES:
                if strat.can_handle(error_mode, details):
                    selected_strategy = strat
                    root_cause = f"Matched {strat.name} for error mode {error_mode}"
                    notes = f"Heuristic match on {strat.name}"
                    break

        # Emit OpenTelemetry Analysis Span
        strat_name = selected_strategy.name if selected_strategy else "NoStrategyAvailable"
        analysis_span = create_analysis_span(root_cause, strat_name, notes)
        analysis_span.end()

        return selected_strategy, root_cause, notes
