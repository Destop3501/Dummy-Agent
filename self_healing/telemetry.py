from typing import Any, Dict, Optional
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

tracer = trace.get_tracer("self_healing_framework")


def create_observation_span(error_mode: str, details: Dict[str, Any]):
    """
    Creates an OpenTelemetry span representing an anomaly observation event.
    """
    span = tracer.start_span("SelfHealing_Observation")
    span.set_attribute("openinference.span.kind", "CHAIN")
    span.set_attribute("healing.phase", "OBSERVE")
    span.set_attribute("healing.error_mode", error_mode)
    for k, v in details.items():
        span.set_attribute(f"healing.observation.{k}", str(v)[:500])
    span.set_status(Status(StatusCode.OK))
    return span


def create_analysis_span(root_cause: str, proposed_strategy: str, diagnostic_notes: str):
    """
    Creates an OpenTelemetry span representing the root-cause diagnosis and strategy selection.
    """
    span = tracer.start_span("SelfHealing_Analysis")
    span.set_attribute("openinference.span.kind", "CHAIN")
    span.set_attribute("healing.phase", "ANALYZE")
    span.set_attribute("healing.root_cause", root_cause)
    span.set_attribute("healing.strategy_selected", proposed_strategy)
    span.set_attribute("healing.diagnostic_notes", diagnostic_notes)
    span.set_status(Status(StatusCode.OK))
    return span


def create_remediation_span(strategy_name: str, input_state: Any, output_state: Any, success: bool = True, notes: str = ""):
    """
    Creates an OpenTelemetry span representing execution of the healing remediation.
    """
    span = tracer.start_span("SelfHealing_Remediation")
    span.set_attribute("openinference.span.kind", "CHAIN")
    span.set_attribute("healing.phase", "REMEDIATE")
    span.set_attribute("healing.strategy", strategy_name)
    span.set_attribute("healing.recovered", success)
    span.set_attribute("healing.input_preview", str(input_state)[:300])
    span.set_attribute("healing.output_preview", str(output_state)[:300])
    if notes:
        span.set_attribute("healing.notes", notes)

    if success:
        span.set_status(Status(StatusCode.OK))
    else:
        span.set_status(Status(StatusCode.ERROR, "Remediation failed"))
    return span
