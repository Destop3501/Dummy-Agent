import os
import sys
import unittest

# Ensure repo root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agent_observability.phase1_agent_host import (
    AgentHostWrapper,
    ToolSchema,
    ToolParameter,
    AgentHostMetadata,
)


class MockExternalCustomerAgent:
    """Mock external customer AI agent with proprietary logic and tool methods."""
    def __init__(self, model_name: str = "mock-gpt-4o"):
        self.model_name = model_name
        self.internal_weights = [0.1, 0.2, 0.3]
        self.calls = []

    def run(self, prompt: str, **kwargs):
        self.calls.append(prompt)
        return f"Response to: {prompt} from {self.model_name}"

    def search_database(self, query: str, limit: int = 5):
        return [{"id": 1, "match": query}]


class TestPhase1AgentHostWrapper(unittest.TestCase):
    def setUp(self):
        self.customer_agent = MockExternalCustomerAgent()
        self.tool_schema = ToolSchema(
            name="search_database",
            description="Searches relational database for matching records.",
            parameters=[
                ToolParameter(name="query", type="string", description="Search query string", required=True),
                ToolParameter(name="limit", type="integer", description="Max items", required=False, default=5),
            ],
            expected_output_type="list",
        )

    def test_encapsulation_without_mutating_agent(self):
        original_weights = list(self.customer_agent.internal_weights)
        wrapper = AgentHostWrapper(
            customer_agent=self.customer_agent,
            tool_schemas=[self.tool_schema],
        )

        # Confirm wrapper holds reference and metadata
        self.assertEqual(wrapper.customer_agent, self.customer_agent)
        self.assertEqual(self.customer_agent.internal_weights, original_weights)
        self.assertIn("search_database", wrapper.tool_schemas)

    def test_run_delegation(self):
        wrapper = AgentHostWrapper(
            customer_agent=self.customer_agent,
            tool_schemas=[self.tool_schema],
        )
        result = wrapper.run("Hello Agent")
        self.assertEqual(result, "Response to: Hello Agent from mock-gpt-4o")
        self.assertEqual(self.customer_agent.calls, ["Hello Agent"])

    def test_tool_execution(self):
        wrapper = AgentHostWrapper(
            customer_agent=self.customer_agent,
            tool_schemas=[self.tool_schema],
            tools={"search_database": self.customer_agent.search_database},
        )
        tool_res = wrapper.execute_tool("search_database", {"query": "deep learning", "limit": 2})
        self.assertEqual(tool_res, [{"id": 1, "match": "deep learning"}])


if __name__ == "__main__":
    unittest.main()
