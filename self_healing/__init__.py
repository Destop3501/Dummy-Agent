"""
Self-Healing Framework for Autonomous AI Agents
Integrates real-time anomaly observation, root-cause diagnosis, multi-tier automated
remediation strategies, and OpenTelemetry / Arize Phoenix observability.
"""

from self_healing.observer import HealthObserver, ObservationEvent
from self_healing.analyzer import DiagnosticAnalyzer
from self_healing.remediation import RemediationExecutor
from self_healing.telemetry import (
    create_observation_span,
    create_analysis_span,
    create_remediation_span,
)

__all__ = [
    "HealthObserver",
    "ObservationEvent",
    "DiagnosticAnalyzer",
    "RemediationExecutor",
    "create_observation_span",
    "create_analysis_span",
    "create_remediation_span",
]
