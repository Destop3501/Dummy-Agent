import uuid
import logging
from typing import Any, Callable, Dict, List, Optional
from agent_observability.phase1_agent_host.models import (
    ToolSchema,
    AgentHostMetadata,
    CustomerAgentProtocol,
)
from agent_observability.phase2_tracing.models import ExecutionTraceSpan, SpanStatus, SpanType
from agent_observability.phase2_tracing.tracer import (
    TraceCollector,
    default_collector,
    trace_prompt,
    trace_tool,
)
from agent_observability.phase3_observer.evaluator import EvaluationNode
from agent_observability.phase3_observer.models import EvaluationVerdict
from agent_observability.phase4_recovery.engine import SelfHealingRecoveryEngine
from agent_observability.phase4_recovery.critic import CriticFunction
from agent_observability.phase4_recovery.models import RecoveryResult

logger = logging.getLogger("agent_observability.host")


class AgentHostWrapper:
    """
    Master host wrapper environment for external customer AI agents.
    Encapsulates the customer agent and its tool schemas without modifying
    the agent's underlying model, weights, or core logic.

    Implements the 4-phase modular architecture:
    1. Uploading & encapsulating the customer agent and schemas
    2. Decorator-based tracking layer for prompt & tool execution traces
    3. Observer & evaluation node detecting missing parameters, syntax errors, and API rejections
    4. Diagnostic loop passing failed traces to Critic for automated context correction & self-recovery
    """

    def __init__(
        self,
        customer_agent: Any,
        tool_schemas: Optional[List[ToolSchema]] = None,
        tools: Optional[Dict[str, Callable[..., Any]]] = None,
        metadata: Optional[AgentHostMetadata] = None,
        collector: Optional[TraceCollector] = None,
        auto_trace: bool = True,
        auto_recover: bool = True,
        critic: Optional[CriticFunction] = None,
        recovery_engine: Optional[SelfHealingRecoveryEngine] = None,
    ):
        """
        Initialize the host environment.

        :param customer_agent: External customer AI agent instance or callable.
        :param tool_schemas: List of ToolSchema objects defining parameter expectations.
        :param tools: Dictionary of tool callables available to the agent.
        :param metadata: Optional metadata descriptor for the agent.
        :param collector: TraceCollector for recording structured JSON traces.
        :param auto_trace: Whether to automatically attach decorator-based tracking to tools & prompts.
        :param auto_recover: Whether to automatically trigger Phase 4 self-healing upon detected failure.
        :param critic: Optional custom CriticFunction.
        :param recovery_engine: Optional custom SelfHealingRecoveryEngine.
        """
        self.customer_agent = customer_agent
        self.collector = collector or TraceCollector()
        self.auto_trace = auto_trace
        self.auto_recover = auto_recover

        self.metadata = metadata or AgentHostMetadata(
            agent_id=f"agent-{uuid.uuid4().hex[:8]}",
            name=getattr(customer_agent, "name", customer_agent.__class__.__name__),
        )

        # Index tool schemas by name
        self.tool_schemas: Dict[str, ToolSchema] = {}
        if tool_schemas:
            for schema in tool_schemas:
                self.tool_schemas[schema.name] = schema

        # Tool registry for raw and wrapped tool executions
        self._raw_tools: Dict[str, Callable[..., Any]] = dict(tools or {})
        self.tools: Dict[str, Callable[..., Any]] = {}

        # Inspect customer_agent for callable methods matching schemas if not explicitly passed
        for name in self.tool_schemas.keys():
            if name not in self._raw_tools and hasattr(customer_agent, name):
                attr = getattr(customer_agent, name)
                if callable(attr):
                    self._raw_tools[name] = attr

        self.evaluator_node = EvaluationNode(
            tool_schemas=self.tool_schemas,
            recovery_router=self._on_detected_failure if self.auto_recover else None,
        )

        # Connect observer node as live listener to traces emitted by Phase 2
        self.collector.add_listener(self.evaluator_node.ingest_trace)

        # Phase 4: Self-Healing Recovery Engine
        if recovery_engine:
            self.recovery_engine = recovery_engine
            if not self.recovery_engine.tool_executor:
                self.recovery_engine.tool_executor = self._raw_execute_tool
        else:
            self.recovery_engine = SelfHealingRecoveryEngine(
                critic=critic or CriticFunction(),
                tool_executor=self._raw_execute_tool,
                max_retries=3,
            )

        for name, func in self._raw_tools.items():
            self._register_traced_tool(name, func)

        self.last_recovery_result: Optional[RecoveryResult] = None

    def _raw_execute_tool(self, tool_name: str, tool_args: Dict[str, Any]) -> Any:
        """Direct, unwrapped execution of tool callable (used by recovery engine during retries)."""
        if tool_name not in self._raw_tools:
            raise KeyError(f"Tool '{tool_name}' is not registered.")
        return self._raw_tools[tool_name](**tool_args)

    def _register_traced_tool(self, name: str, func: Callable[..., Any]) -> None:
        """Wrap tool callable with tracking layer."""
        if self.auto_trace:
            self.tools[name] = trace_tool(name=name, collector=self.collector, reraise=True)(func)
        else:
            self.tools[name] = func

    def _on_detected_failure(self, verdict: EvaluationVerdict, span: ExecutionTraceSpan) -> None:
        """Internal callback invoked when EvaluationNode routes a failed trace."""
        logger.info(f"Observer routed failure for span {span.span_id}. Handing over to Critic.")
        # Trigger diagnostic loop and recovery
        self.last_recovery_result = self.recovery_engine.handle_failed_trace(
            verdict=verdict,
            span=span,
            custom_executor=self._raw_execute_tool,
        )

    def register_tool(self, schema: ToolSchema, func: Optional[Callable[..., Any]] = None) -> None:
        """Register or update a tool schema and callable in the host environment."""
        self.tool_schemas[schema.name] = schema
        self.evaluator_node.register_tool_schema(schema)
        if func:
            self._raw_tools[schema.name] = func
            self._register_traced_tool(schema.name, func)

    def get_tool_schema(self, tool_name: str) -> Optional[ToolSchema]:
        """Retrieve the registered schema for a tool."""
        return self.tool_schemas.get(tool_name)

    def execute_tool(self, tool_name: str, tool_args: Dict[str, Any]) -> Any:
        """
        Safely execute a tool through the host environment with full self-healing recovery.
        If the primary tool fails, the error is detected, diagnosed by the Critic,
        and automatically retried with corrected context without human intervention.
        """
        if tool_name not in self.tools:
            raise KeyError(f"Tool '{tool_name}' is not registered in the host environment.")

        try:
            return self.tools[tool_name](**tool_args)
        except Exception as exc:
            if self.auto_recover and self.last_recovery_result and self.last_recovery_result.success:
                # Return recovered output transparently to primary agent workflow
                return self.last_recovery_result.recovered_output
            raise

    def run(self, prompt: str, **kwargs: Any) -> Any:
        """
        Execute the wrapped customer agent on a given prompt.
        Delegates cleanly to the customer agent's own execution method
        while recording traces.
        """
        entrypoint: Optional[Callable[..., Any]] = None
        for candidate in ["run", "execute", "invoke", "__call__"]:
            if hasattr(self.customer_agent, candidate):
                attr = getattr(self.customer_agent, candidate)
                if callable(attr):
                    entrypoint = attr
                    break

        if entrypoint is None:
            if callable(self.customer_agent):
                entrypoint = self.customer_agent
            else:
                raise AttributeError(
                    f"Customer agent {type(self.customer_agent)} has no executable entrypoint "
                    "(run, execute, invoke, or __call__)."
                )

        if self.auto_trace:
            traced_runner = trace_prompt(name=self.metadata.name, collector=self.collector)(entrypoint)
            return traced_runner(prompt, **kwargs)
        else:
            return entrypoint(prompt, **kwargs)
