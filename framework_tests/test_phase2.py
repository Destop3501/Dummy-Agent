import json
import os
import sys
import time
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agent_observability.phase1_agent_host import (
    AgentHostWrapper,
    ToolSchema,
    ToolParameter,
)
from agent_observability.phase2_tracing import (
    TraceCollector,
    SpanStatus,
    SpanType,
    trace_tool,
    trace_prompt,
)


class MockAgentWithTools:
    def __init__(self):
        self.name = "TestAgent"

    def calculate_metrics(self, x: int, y: int):
        time.sleep(0.01)  # Simulate measurable latency
        return x / y

    def run(self, prompt: str):
        return f"Processed: {prompt}"


class TestPhase2ExecutionTracing(unittest.TestCase):
    def setUp(self):
        self.collector = TraceCollector()
        self.agent = MockAgentWithTools()

    def test_tool_tracing_success_latency_and_inputs(self):
        @trace_tool(name="calc", collector=self.collector)
        def calc(x: int, y: int):
            time.sleep(0.015)
            return x + y

        result = calc(10, 20)
        self.assertEqual(result, 30)

        traces = self.collector.get_all_traces()
        self.assertEqual(len(traces), 1)
        span = traces[0]

        self.assertEqual(span.name, "calc")
        self.assertEqual(span.span_type, SpanType.TOOL)
        self.assertEqual(span.inputs, {"x": 10, "y": 20})
        self.assertEqual(span.outputs, 30)
        self.assertEqual(span.status, SpanStatus.SUCCESS)
        self.assertIsNotNone(span.span_id)
        self.assertIsNotNone(span.trace_id)
        self.assertGreater(span.latency_ms, 10.0)  # At least 10ms
        self.assertIsNone(span.error)

    def test_tool_tracing_error_payload_and_stack_trace(self):
        @trace_tool(name="failing_tool", collector=self.collector, reraise=False)
        def fail_func():
            raise ValueError("Invalid configuration provided to external API")

        output = fail_func()
        self.assertEqual(output["status"], "failed")

        traces = self.collector.get_all_traces()
        self.assertEqual(len(traces), 1)
        span = traces[0]

        self.assertEqual(span.status, SpanStatus.FAILED)
        self.assertIsNotNone(span.error)
        self.assertEqual(span.error.error_type, "ValueError")
        self.assertIn("Invalid configuration provided", span.error.message)
        self.assertIn("Traceback (most recent call last)", span.error.stack_trace)
        self.assertIn("fail_func", span.error.stack_trace)

        # Verify structured JSON serialization
        json_output = span.to_json()
        parsed = json.loads(json_output)
        self.assertEqual(parsed["name"], "failing_tool")
        self.assertEqual(parsed["error"]["error_type"], "ValueError")
        self.assertIn("stack_trace", parsed["error"])

    def test_host_wrapper_auto_tracing_integration(self):
        calc_schema = ToolSchema(
            name="calculate_metrics",
            description="Division calculation",
            parameters=[
                ToolParameter(name="x", type="integer"),
                ToolParameter(name="y", type="integer"),
            ],
        )

        wrapper = AgentHostWrapper(
            customer_agent=self.agent,
            tool_schemas=[calc_schema],
            tools={"calculate_metrics": self.agent.calculate_metrics},
            collector=self.collector,
            auto_trace=True,
            auto_recover=False,
        )

        # Call prompt
        agent_out = wrapper.run("Hello test")
        self.assertEqual(agent_out, "Processed: Hello test")

        # Call tool with success
        res = wrapper.execute_tool("calculate_metrics", {"x": 10, "y": 2})
        self.assertEqual(res, 5.0)

        # Call tool with error (ZeroDivisionError)
        with self.assertRaises(ZeroDivisionError):
            wrapper.execute_tool("calculate_metrics", {"x": 10, "y": 0})

        traces = self.collector.get_all_traces()
        self.assertEqual(len(traces), 3)

        # First trace: Agent prompt run
        self.assertEqual(traces[0].span_type, SpanType.PROMPT)
        # Second trace: Successful tool execution
        self.assertEqual(traces[1].name, "calculate_metrics")
        self.assertEqual(traces[1].status, SpanStatus.SUCCESS)
        # Third trace: Failed tool execution with exact stack trace
        self.assertEqual(traces[2].name, "calculate_metrics")
        self.assertEqual(traces[2].status, SpanStatus.FAILED)
        self.assertEqual(traces[2].error.error_type, "ZeroDivisionError")
        self.assertIn("division by zero", traces[2].error.message)


if __name__ == "__main__":
    unittest.main()
