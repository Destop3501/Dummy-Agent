import json
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agent_observability.phase1_agent_host import (
    AgentHostWrapper,
    ToolSchema,
    ToolParameter,
    AgentHostMetadata,
)
from agent_observability.phase2_tracing import (
    TraceCollector,
    SpanStatus,
    SpanType,
)
from agent_observability.phase3_observer import (
    EvaluationNode,
    EvaluationVerdict,
    FailureCategory,
)
from agent_observability.phase4_recovery import (
    CriticFunction,
    RecoveryStrategyType,
)


class CustomerTradingAgent:
    """Mock external customer AI agent."""
    def __init__(self):
        self.model = "Proprietary-LLM-v2"
        self.weights_hash = "0xdeadbeef"

    def run(self, prompt: str):
        return f"Trading Agent processed: {prompt}"

    def query_stock_price(self, ticker: str, days: int = 1):
        if ticker == "INVALID_TICKER_404":
            raise LookupError("API 404: Ticker not found on market exchange")
        return {"ticker": ticker, "price": 182.50, "days": days}

    def execute_order(self, ticker: str, quantity: int, order_type: str = "BUY"):
        if not isinstance(quantity, int):
            raise TypeError(f"quantity must be integer, got {type(quantity).__name__}")
        return {"status": "FILLED", "order_id": "ORD-9912", "ticker": ticker, "qty": quantity}


class TestAllFourPhasesIntegrated(unittest.TestCase):
    def setUp(self):
        self.agent = CustomerTradingAgent()
        self.stock_schema = ToolSchema(
            name="query_stock_price",
            description="Fetches live market price for a given ticker",
            parameters=[
                ToolParameter(name="ticker", type="string", required=True),
                ToolParameter(name="days", type="integer", required=False, default=1),
            ],
            expected_output_type="dict",
        )
        self.order_schema = ToolSchema(
            name="execute_order",
            description="Submits trade order to execution exchange",
            parameters=[
                ToolParameter(name="ticker", type="string", required=True),
                ToolParameter(name="quantity", type="integer", required=True),
                ToolParameter(name="order_type", type="string", required=False, default="BUY"),
            ],
            expected_output_type="dict",
        )

        self.critic = CriticFunction(
            fallback_endpoints={"INVALID_TICKER_404": "AAPL"}
        )

    def test_full_four_phase_lifecycle(self):
        # ==========================================
        # PHASE 1: Uploading the Customer Agent
        # ==========================================
        wrapper = AgentHostWrapper(
            customer_agent=self.agent,
            tool_schemas=[self.stock_schema, self.order_schema],
            metadata=AgentHostMetadata(
                agent_id="agent-quant-007",
                name="CustomerTradingAgent",
                version="2.1.0",
            ),
            critic=self.critic,
            auto_trace=True,
            auto_recover=True,
        )

        # Agent weights & core logic are intact and unmutated
        self.assertEqual(self.agent.weights_hash, "0xdeadbeef")
        self.assertEqual(wrapper.metadata.agent_id, "agent-quant-007")

        # ==========================================
        # PHASE 2: Creating Execution Traces
        # ==========================================
        # Agent prompt run is intercepted and traced
        prompt_res = wrapper.run("Evaluate portfolio balance")
        self.assertIn("Trading Agent processed", prompt_res)

        traces = wrapper.collector.get_all_traces()
        self.assertEqual(len(traces), 1)
        prompt_span = traces[0]
        self.assertEqual(prompt_span.span_type, SpanType.PROMPT)
        self.assertIsNotNone(prompt_span.span_id)
        self.assertIsNotNone(prompt_span.latency_ms)

        # Verify JSON structured serialization contains expected telemetry fields
        json_trace = json.loads(prompt_span.to_json())
        self.assertIn("span_id", json_trace)
        self.assertIn("latency_ms", json_trace)
        self.assertIn("inputs", json_trace)

        # ==========================================
        # PHASE 3 & 4: Detecting Failures & Self-Recovery
        # ==========================================
        # Test 1: API Rejection (404 ticker) -> Critic detects 404 -> fallbacks to AAPL -> recovers cleanly
        stock_result = wrapper.execute_tool(
            "query_stock_price",
            {"ticker": "INVALID_TICKER_404", "days": 1}
        )
        self.assertIsNotNone(stock_result)
        self.assertEqual(stock_result["ticker"], "AAPL")
        self.assertEqual(stock_result["price"], 182.50)

        # Test 2: Type Mismatch (quantity passed as string "50") -> Critic diagnoses & coerces to int 50 -> succeeds
        order_result = wrapper.execute_tool(
            "execute_order",
            {"ticker": "AAPL", "quantity": "50", "order_type": "BUY"}
        )
        self.assertIsNotNone(order_result)
        self.assertEqual(order_result["status"], "FILLED")
        self.assertEqual(order_result["qty"], 50)

        # Inspect final traces: confirm statuses are RECOVERED and metadata is attached
        all_traces = wrapper.collector.get_all_traces()
        # Traces: 1 prompt span + 2 tool spans
        self.assertEqual(len(all_traces), 3)

        stock_span = all_traces[1]
        self.assertEqual(stock_span.status, SpanStatus.RECOVERED)
        self.assertEqual(stock_span.metadata["recovered_by"], "CriticSelfHealingEngine")

        order_span = all_traces[2]
        self.assertEqual(order_span.status, SpanStatus.RECOVERED)
        self.assertEqual(order_span.metadata["recovered_by"], "CriticSelfHealingEngine")


if __name__ == "__main__":
    unittest.main()
