"""
Agent Observability & Self-Recovery Framework

A modular, four-phase architecture:
1. Uploading the Customer Agent (AgentHostWrapper, ToolSchema, ToolParameter)
2. Creating Execution Traces (TraceCollector, trace_tool, trace_prompt, ExecutionTraceSpan)
3. Observing and Detecting Failures (EvaluationNode, EvaluationVerdict, FailureCategory)
4. Self-Healing and Recovery (SelfHealingRecoveryEngine, CriticFunction, CriticDiagnosis)
"""

from agent_observability.phase1_agent_host import (
    AgentHostWrapper,
    ToolSchema,
    ToolParameter,
    AgentHostMetadata,
    CustomerAgentProtocol,
)
from agent_observability.phase2_tracing import (
    TraceCollector,
    ExecutionTraceSpan,
    SpanStatus,
    SpanType,
    ErrorPayload,
    trace_tool,
    trace_prompt,
    default_collector,
)
from agent_observability.phase3_observer import (
    EvaluationNode,
    EvaluationVerdict,
    FailureCategory,
)
from agent_observability.phase4_recovery import (
    SelfHealingRecoveryEngine,
    CriticFunction,
    CriticDiagnosis,
    RecoveryResult,
    RecoveryStrategyType,
)

__all__ = [
    # Phase 1
    "AgentHostWrapper",
    "ToolSchema",
    "ToolParameter",
    "AgentHostMetadata",
    "CustomerAgentProtocol",
    # Phase 2
    "TraceCollector",
    "ExecutionTraceSpan",
    "SpanStatus",
    "SpanType",
    "ErrorPayload",
    "trace_tool",
    "trace_prompt",
    "default_collector",
    # Phase 3
    "EvaluationNode",
    "EvaluationVerdict",
    "FailureCategory",
    # Phase 4
    "SelfHealingRecoveryEngine",
    "CriticFunction",
    "CriticDiagnosis",
    "RecoveryResult",
    "RecoveryStrategyType",
]
