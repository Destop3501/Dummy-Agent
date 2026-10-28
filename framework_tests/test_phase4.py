import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agent_observability.phase1_agent_host import (
    AgentHostWrapper,
    ToolSchema,
    ToolParameter,
)
from agent_observability.phase2_tracing import (
    ExecutionTraceSpan,
    SpanStatus,
    SpanType,
    ErrorPayload,
)
from agent_observability.phase3_observer import (
    EvaluationNode,
    EvaluationVerdict,
    FailureCategory,
)
from agent_observability.phase4_recovery import (
    CriticFunction,
    SelfHealingRecoveryEngine,
    RecoveryStrategyType,
)


class MockCustomerAgent:
    """External customer agent with simulated real-world tool scenarios."""
    def __init__(self):
        self.name = "CustomerFinanceAgent"

    def fetch_api_data(self, url: str):
        if "404" in url or "nonexistent" in url:
            raise ConnectionError(f"HTTP 404: Endpoint {url} not found")
        return {"status": 200, "data": f"content from {url}"}

    def save_report(self, filename: str, content: str):
        if "{{" in content:
            raise ValueError("SyntaxError: content contains unparsed template variable")
        return {"status": "saved", "path": filename, "bytes": len(content)}

    def calculate_tax(self, amount: int, rate: float):
        if not isinstance(amount, (int, float)):
            raise TypeError(f"amount must be numeric, got {type(amount).__name__}")
        return amount * rate


class TestPhase4SelfHealingAndRecovery(unittest.TestCase):
    def setUp(self):
        self.agent = MockCustomerAgent()
        self.critic = CriticFunction(fallback_endpoints={"nonexistent": "posts/1", "404": "posts/1"})

    def test_critic_diagnoses_and_corrects_api_rejection(self):
        # 1. Simulate a failed span with 404 error
        span = ExecutionTraceSpan(
            span_type=SpanType.TOOL,
            name="fetch_api_data",
            inputs={"url": "https://api.example.com/nonexistent_data"},
            status=SpanStatus.FAILED,
            error=ErrorPayload(
                error_type="ConnectionError",
                message="HTTP 404: Endpoint not found",
                stack_trace="Traceback...",
            ),
        )
        verdict = EvaluationVerdict(
            is_valid=False,
            failure_category=FailureCategory.API_REJECTION,
            diagnostic_message="API Rejection 404 detected",
            deviations=["HTTP 404"],
            span_id=span.span_id,
            trace_id=span.trace_id,
            tool_name="fetch_api_data",
            tool_inputs=span.inputs,
        )

        diagnosis = self.critic.analyze(span=span, schema=None, verdict=verdict)
        self.assertEqual(diagnosis.strategy, RecoveryStrategyType.RETRY_WITH_FALLBACK)
        self.assertIn("url", diagnosis.corrected_inputs)
        self.assertIn("posts/1", diagnosis.corrected_inputs["url"])

    def test_critic_diagnoses_and_hydrates_syntax_error(self):
        # 2. Simulate unparsed template syntax error
        span = ExecutionTraceSpan(
            span_type=SpanType.TOOL,
            name="save_report",
            inputs={"filename": "report.md", "content": "{{fetch_api.output.body}}"},
            status=SpanStatus.FAILED,
            error=ErrorPayload(
                error_type="ValueError",
                message="SyntaxError: content contains unparsed template variable",
                stack_trace="Traceback...",
            ),
        )
        verdict = EvaluationVerdict(
            is_valid=False,
            failure_category=FailureCategory.SYNTAX_ERROR,
            diagnostic_message="Syntax error detected",
            deviations=["unparsed template"],
            span_id=span.span_id,
            trace_id=span.trace_id,
            tool_name="save_report",
            tool_inputs=span.inputs,
        )

        diagnosis = self.critic.analyze(span=span, schema=None, verdict=verdict)
        self.assertEqual(diagnosis.strategy, RecoveryStrategyType.HYDRATE_SYNTAX)
        self.assertNotIn("{{", diagnosis.corrected_inputs["content"])
        self.assertEqual(diagnosis.corrected_inputs["content"], "hydrated_content_payload")

    def test_end_to_end_self_healing_without_human_intervention(self):
        # 3. Full end-to-end self recovery through AgentHostWrapper
        fetch_schema = ToolSchema(
            name="fetch_api_data",
            description="Fetches external API data",
            parameters=[ToolParameter(name="url", type="string", required=True)],
            expected_output_type="dict",
        )
        save_schema = ToolSchema(
            name="save_report",
            description="Saves report to disk",
            parameters=[
                ToolParameter(name="filename", type="string", required=True),
                ToolParameter(name="content", type="string", required=True),
            ],
            expected_output_type="dict",
        )

        wrapper = AgentHostWrapper(
            customer_agent=self.agent,
            tool_schemas=[fetch_schema, save_schema],
            auto_trace=True,
            auto_recover=True,
            critic=self.critic,
        )

        # Execute tool with faulty 404 URL:
        # Wrapper catches error -> Observer evaluates failure -> Critic diagnoses root cause ->
        # SelfHealingRecoveryEngine re-executes with corrected URL -> returns recovered payload seamlessly!
        recovered_result = wrapper.execute_tool(
            "fetch_api_data",
            {"url": "https://api.example.com/nonexistent_data"}
        )

        self.assertIsNotNone(recovered_result)
        self.assertEqual(recovered_result["status"], 200)
        self.assertIn("posts/1", recovered_result["data"])

        # Verify that the span status was updated to RECOVERED in telemetry
        traces = wrapper.collector.get_all_traces()
        recovered_span = traces[0]
        self.assertEqual(recovered_span.status, SpanStatus.RECOVERED)
        self.assertEqual(recovered_span.metadata["recovered_by"], "CriticSelfHealingEngine")

        # Execute tool with unparsed template syntax error:
        recovered_file = wrapper.execute_tool(
            "save_report",
            {"filename": "summary.md", "content": "{{unparsed_var}}"}
        )
        self.assertIsNotNone(recovered_file)
        self.assertEqual(recovered_file["status"], "saved")


if __name__ == "__main__":
    unittest.main()
