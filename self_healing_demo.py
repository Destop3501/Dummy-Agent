import sys
import os
import time

if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

from dummyAgent import Agent, client, system_prompt, tools, px

TEST_SCENARIOS = {
    "1": {
        "title": "Tool Execution Failure (HTTP 404 API Endpoint)",
        "prompt": "Fetch data from https://jsonplaceholder.typicode.com/nonexistent_page_404, summarize it, and save to 'fail_getter.md'.",
        "description": "API returns 404 Not Found. Baseline halts; Self-Healing routes to canonical endpoint / resilient fallback.",
    },
    "2": {
        "title": "Silent Template Hallucination Error",
        "prompt": "Save the raw unparsed template string '{{fetch_api_data.output.body}}' into 'template.md' using save_the_file tool.",
        "description": "LLM outputs unparsed mustache template syntax. Baseline rejects; Self-Healing hydrator injects concrete content.",
    },
    "3": {
        "title": "Infinite Loop & Polling Stagnation",
        "prompt": "Keep checking the temperature of San Francisco repeatedly until it reaches 100 degrees.",
        "description": "Agent polls invariant 75°F state. Baseline crashes at turn limit; Self-Healing loop breaker detects cycle and guides graceful exit.",
    },
    "4": {
        "title": "Unknown City / Domain Entity Error",
        "prompt": "What is the temperature in Atlantis?",
        "description": "Tool raises ValueError for unknown city. Baseline fails; Self-Healing provides domain-aware resolution and guided fallback.",
    },
}


def print_banner():
    print("\n" + "=" * 70)
    print("      🚀 AUTONOMOUS SELF-HEALING FRAMEWORK DEMONSTRATION")
    print("         Observability with Arize Phoenix & OpenTelemetry")
    print("=" * 70)
    print("Phoenix UI Dashboard: http://localhost:6006")
    print("=" * 70)


def print_menu():
    print_banner()
    print("\nAvailable Demonstration Modes:")
    print("  [1-4] Run Scenario with Side-by-Side Comparison (Baseline vs Self-Healed)")
    print("  [A]   Run Automated Benchmark Suite (All 4 scenarios side-by-side)")
    print("  [T]   Toggle Live Agent Execution (Interactive Single Prompt)")
    print("  [Q]   Quit and close Phoenix tracing server")
    print("\nScenarios:")
    for key, sc in TEST_SCENARIOS.items():
        print(f"  {key}. {sc['title']}")
    print("-" * 70)


def run_single_comparison(scenario_key: str):
    sc = TEST_SCENARIOS.get(scenario_key)
    if not sc:
        print(f"Invalid scenario: {scenario_key}")
        return

    prompt = sc["prompt"]
    print("\n" + "=" * 70)
    print(f"SCENARIO: {sc['title']}")
    print(f"Description: {sc['description']}")
    print(f"User Prompt: \"{prompt}\"")
    print("=" * 70)

    # 1. RUN BASELINE (Self-Healing OFF)
    print("\n🔴 --- [1/2] RUNNING BASELINE (Self-Healing DISABLED) ---")
    baseline_agent = Agent(client, system_prompt, tools, max_turns=5, self_healing=False)
    t0 = time.time()
    try:
        baseline_result = baseline_agent(prompt)
    except Exception as e:
        baseline_result = f"Exception: {e}"
    baseline_lat = int((time.time() - t0) * 1000)

    print(f"⏱️ Baseline Latency: {baseline_lat}ms")
    print(f"❌ Baseline Outcome: {str(baseline_result)[:160]}...")
    print(f"📊 Had Error Flag: {baseline_agent.had_error} | Error Mode: {baseline_agent.last_error_mode}")

    # 2. RUN SELF-HEALED (Self-Healing ON)
    print("\n🟢 --- [2/2] RUNNING SELF-HEALING (Autonomous Remediation ENABLED) ---")
    healed_agent = Agent(client, system_prompt, tools, max_turns=5, self_healing=True)
    t0 = time.time()
    try:
        healed_result = healed_agent(prompt)
    except Exception as e:
        healed_result = f"Exception: {e}"
    healed_lat = int((time.time() - t0) * 1000)

    print(f"⏱️ Healed Latency: {healed_lat}ms")
    print(f"✅ Self-Healed Outcome: {str(healed_result)[:160]}...")
    print(f"✨ Self-Healed: {healed_agent.is_healed}")
    if healed_agent.healing_log:
        print(f"🛠️ Remediation Applied: {'; '.join(healed_agent.healing_log)}")

    print("\n📊 Check Phoenix traces live at http://localhost:6006 to view:")
    print("   - Red/ERROR span for the Baseline run")
    print("   - Green/SELF_HEALED span with SelfHealing_* child spans for the Remediated run")
    print("-" * 70)


def run_automated_benchmark():
    print("\n" + "=" * 75)
    print("           📊 RUNNING AUTOMATED SELF-HEALING BENCHMARK SUITE")
    print("=" * 75)

    results = []

    for key, sc in TEST_SCENARIOS.items():
        print(f"\nEvaluating Scenario {key}: {sc['title']}...")
        prompt = sc["prompt"]

        # Baseline
        b_agent = Agent(client, system_prompt, tools, max_turns=5, self_healing=False)
        try:
            b_res = b_agent(prompt)
            b_status = "❌ FAILED" if (b_agent.had_error or str(b_res).startswith("Error:")) else "⚠️ UNEXPECTED_OK"
        except Exception:
            b_status = "❌ CRASHED"

        # Healed
        h_agent = Agent(client, system_prompt, tools, max_turns=5, self_healing=True)
        try:
            h_res = h_agent(prompt)
            h_status = "✅ HEALED" if (h_agent.is_healed or not h_agent.had_error) else "❌ FAILED"
        except Exception:
            h_status = "❌ CRASHED"

        remedy = h_agent.healing_log[0] if h_agent.healing_log else "None required"

        results.append({
            "key": key,
            "title": sc["title"][:28],
            "baseline": b_status,
            "healed": h_status,
            "remedy": remedy[:35],
        })

    print("\n" + "=" * 75)
    print(f"{'#':<3} | {'Scenario':<28} | {'Baseline':<12} | {'Self-Healed':<12} | {'Remediation Applied':<35}")
    print("-" * 75)
    for r in results:
        print(f"{r['key']:<3} | {r['title']:<28} | {r['baseline']:<12} | {r['healed']:<12} | {r['remedy']:<35}")
    print("=" * 75)
    print("All traces successfully recorded in Arize Phoenix: http://localhost:6006\n")


if __name__ == "__main__":
    try:
        while True:
            print_menu()
            try:
                choice = input("Select an option (1-4, A for all, Q to quit): ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                print("\nExiting...")
                break

            if choice in ("q", "quit", "exit"):
                print("\nShutting down demonstration and tracing server...")
                break
            elif choice in ("1", "2", "3", "4"):
                run_single_comparison(choice)
                input("\nPress Enter to return to menu...")
            elif choice == "a":
                run_automated_benchmark()
                input("\nPress Enter to return to menu...")
            else:
                print(f"Unknown option '{choice}'. Please select from the menu.")
    finally:
        px.close_app()
        print("Tracing server closed.")
