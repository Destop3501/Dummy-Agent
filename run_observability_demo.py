import json
import time
from agent_observability import (
    AgentHostWrapper,
    ToolSchema,
    ToolParameter,
    AgentHostMetadata,
    CriticFunction,
)


class CustomerSupportAgent:
    """External Customer AI Agent with real business logic and tools."""
    def __init__(self):
        self.name = "EnterpriseSupportBot"
        self.version = "3.2.1"

    def run(self, user_query: str) -> str:
        return f"SupportBot responded to query: '{user_query}'"

    def fetch_user_account(self, user_id: int):
        if not isinstance(user_id, int):
            raise TypeError(f"user_id must be integer, got {type(user_id).__name__}")
        return {"user_id": user_id, "name": "Alice Johnson", "tier": "Enterprise VIP"}

    def query_remote_service(self, endpoint: str):
        if "404" in endpoint or "nonexistent" in endpoint:
            raise ConnectionError(f"HTTP 404: Endpoint {endpoint} not found on server")
        return {"status": 200, "data": f"Healthy response from {endpoint}"}

    def save_ticket_memo(self, ticket_id: str, memo: str):
        if "{{" in memo:
            raise ValueError(f"Syntax error: memo contains unparsed template variable: {memo}")
        return {"status": "success", "ticket_id": ticket_id, "saved_bytes": len(memo)}


def main():
    print("=" * 80)
    print(" AGENT OBSERVABILITY & SELF-RECOVERY FRAMEWORK DEMO")
    print("=" * 80)

    # ----------------------------------------------------
    # Phase 1: Uploading the Customer Agent
    # ----------------------------------------------------
    print("\n[Phase 1] Uploading Customer Agent and Schemas...")
    agent = CustomerSupportAgent()

    account_schema = ToolSchema(
        name="fetch_user_account",
        description="Retrieves customer profile and VIP status",
        parameters=[ToolParameter(name="user_id", type="integer", required=True)],
        expected_output_type="dict",
    )
    service_schema = ToolSchema(
        name="query_remote_service",
        description="Calls external microservice endpoint",
        parameters=[ToolParameter(name="endpoint", type="string", required=True)],
        expected_output_type="dict",
    )
    memo_schema = ToolSchema(
        name="save_ticket_memo",
        description="Persists ticket documentation",
        parameters=[
            ToolParameter(name="ticket_id", type="string", required=True),
            ToolParameter(name="memo", type="string", required=True),
        ],
        expected_output_type="dict",
    )

    critic = CriticFunction(
        fallback_endpoints={
            "api.internal/v1/nonexistent_service_404": "api.internal/v1/healthy_service"
        }
    )

    wrapper = AgentHostWrapper(
        customer_agent=agent,
        tool_schemas=[account_schema, service_schema, memo_schema],
        metadata=AgentHostMetadata(
            agent_id="agt-support-01",
            name="EnterpriseSupportBot",
            version="3.2.1",
        ),
        critic=critic,
        auto_trace=True,
        auto_recover=True,
    )
    print("   Customer agent encapsulated seamlessly without modifying core logic.")

    # ----------------------------------------------------
    # Phase 2: Creating Execution Traces (Prompt Execution)
    # ----------------------------------------------------
    print("\n[Phase 2] Intercepting Prompt Workflow with Decorator-based Tracking...")
    reply = wrapper.run("Check customer account status for user #4092")
    print(f"   Agent response: {reply}")

    # ----------------------------------------------------
    # Phase 3 & 4: Failure Detection & Self-Healing Scenarios
    # ----------------------------------------------------
    print("\n[Phase 3 & 4] Executing Tool Calls with Automated Failure Detection & Self-Recovery:\n")

    # Scenario A: Type Mismatch (user_id passed as string "4092" instead of integer)
    print("--- Scenario A: Type Mismatch ---")
    print("   Executing: fetch_user_account(user_id='4092')")
    account_info = wrapper.execute_tool("fetch_user_account", {"user_id": "4092"})
    print(f"   Self-Healed Output: {account_info}")

    # Scenario B: API Rejection (HTTP 404 URL)
    print("\n--- Scenario B: API Rejection ---")
    print("   Executing: query_remote_service(endpoint='https://api.internal/v1/nonexistent_service_404')")
    service_info = wrapper.execute_tool(
        "query_remote_service",
        {"endpoint": "https://api.internal/v1/nonexistent_service_404"}
    )
    print(f"   Self-Healed Output: {service_info}")

    # Scenario C: Syntax Error (Unparsed template expression)
    print("\n--- Scenario C: Syntax Error (Unparsed Template Variable) ---")
    print("   Executing: save_ticket_memo(ticket_id='TCK-100', memo='{{fetch_user_account.output.name}} logged in')")
    memo_info = wrapper.execute_tool(
        "save_ticket_memo",
        {"ticket_id": "TCK-100", "memo": "{{fetch_user_account.output.name}} logged in"}
    )
    print(f"   Self-Healed Output: {memo_info}")

    # ----------------------------------------------------
    # Telemetry Summary
    # ----------------------------------------------------
    print("\n" + "=" * 80)
    print(" STRUCTURED EXECUTION TRACES (PHASE 2 TELEMETRY AUDIT)")
    print("=" * 80)
    all_traces = wrapper.collector.get_all_traces()
    for idx, trace in enumerate(all_traces, 1):
        print(f"\n[Trace {idx}] Type: {trace.span_type} | Name: {trace.name} | Status: {trace.status} | Latency: {trace.latency_ms}ms")
        print(f"   Span ID: {trace.span_id} | Trace ID: {trace.trace_id}")
        if trace.metadata.get("recovered_by"):
            print(f"   Recovery: {trace.metadata['recovered_by']} (Retries: {trace.metadata.get('retries_taken')})")
        print(f"   Inputs: {json.dumps(trace.inputs)}")
        print(f"   Output: {json.dumps(trace.outputs)}")

    print("\nDemo completed successfully!")


if __name__ == "__main__":
    main()
