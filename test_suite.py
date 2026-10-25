import sys
import os

# Ensure UTF-8 output encoding on Windows consoles
if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

from dummyAgent import Agent, client, system_prompt, tools, px

HEALING_ENABLED = True


def print_menu():
    mode_str = "🟢 ENABLED (Autonomous Self-Healing)" if HEALING_ENABLED else "🔴 DISABLED (Baseline Failure Mode)"
    print("\n" + "=" * 55)
    print("      AGENT FAILURE & SELF-HEALING TEST SUITE")
    print(f"      Current Mode: {mode_str}")
    print("=" * 55)
    print("1. Tool Execution Failure (404 API Endpoint)")
    print("2. Silent Template Hallucination Error")
    print("3. Infinite Loop & Stagnation Deadlock")
    print("4. Unknown City / Domain Entity Error")
    print("m. Toggle Self-Healing Mode (ON/OFF)")
    print("q. Quit and Stop Server")
    print("=" * 55)


if __name__ == "__main__":
    try:
        while True:
            print_menu()
            try:
                choice = input("Select test mode (1-4, 'm' to toggle, or 'q' to quit): ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                print("\nExiting...")
                break

            if choice in ("q", "quit", "exit"):
                print("\nStopping test suite and tracing server...")
                break
            elif choice == "m":
                HEALING_ENABLED = not HEALING_ENABLED
                state = "🟢 ENABLED" if HEALING_ENABLED else "🔴 DISABLED"
                print(f"\nSelf-Healing Framework is now {state}.")
                continue

            test_agent = Agent(client, system_prompt, tools, max_turns=5, self_healing=HEALING_ENABLED)
            mode_tag = "[SELF-HEALING ACTIVE]" if HEALING_ENABLED else "[BASELINE FAILURE]"

            if choice == "1":
                print(f"\n--- Running Test 1: Tool Execution Failure (404 API) {mode_tag} ---")
                print(test_agent("Fetch data from https://jsonplaceholder.typicode.com/nonexistent_page_404, summarize it, and save to 'fail_getter.md'."))
            elif choice == "2":
                print(f"\n--- Running Test 2: Silent Template Error {mode_tag} ---")
                print(test_agent("Save the raw unparsed template string '{{fetch_api_data.output.body}}' into 'template.md' using save_the_file tool."))
            elif choice == "3":
                print(f"\n--- Running Test 3: Infinite Loop Error {mode_tag} ---")
                print(test_agent("Keep checking the temperature of San Francisco repeatedly until it reaches 100 degrees."))
            elif choice == "4":
                print(f"\n--- Running Test 4: Unknown City Tool Error {mode_tag} ---")
                print(test_agent("What is the temperature in Atlantis?"))
            else:
                print(f"Invalid choice '{choice}'. Please enter 1-4, 'm', or 'q'.")
                continue

            if test_agent.is_healed:
                print(f"\n✨ Self-Healing Recovery Triggered: {'; '.join(test_agent.healing_log)}")
            elif test_agent.had_error:
                print(f"\n⚠️ Failure observed (Self-Healing was {'OFF' if not HEALING_ENABLED else 'Unsuccessful'}).")

            print("\n📊 Check traces live in Arize Phoenix at http://localhost:6006")
    finally:
        px.close_app()
        print("Tracing server closed.")
