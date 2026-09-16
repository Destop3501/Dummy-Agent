import sys
import os

# Ensure UTF-8 output encoding on Windows consoles
if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

from dummyAgent import agent, px

def print_menu():
    print("\n" + "=" * 45)
    print("      AGENT FAILURE MODE TEST SUITE")
    print("=" * 45)
    print("1. Tool Execution Failure (404 API)")
    print("2. Silent Template Error")
    print("3. Infinite Loop Error")
    print("4. Unknown City Tool Error")
    print("q. Quit and Stop Server")
    print("=" * 45)

if __name__ == "__main__":
    try:
        while True:
            print_menu()
            try:
                choice = input("Select test mode (1-4 or 'q' to quit): ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                print("\nExiting...")
                break

            if choice in ("q", "quit", "exit"):
                print("\nStopping test suite and tracing server...")
                break
            elif choice == "1":
                print("\n--- Running Test 1: Tool Execution Failure (404 API) ---")
                print(agent("Fetch data from https://jsonplaceholder.typicode.com/nonexistent_page_404, summarize it, and save to 'fail_getter.md'."))
            elif choice == "2":
                print("\n--- Running Test 2: Silent Template Error ---")
                print(agent("Save the raw unparsed template string '{{fetch_api_data.output.body}}' into 'template.md' using save_the_file tool."))
            elif choice == "3":
                print("\n--- Running Test 3: Infinite Loop Error ---")
                print(agent("Keep checking the temperature of San Francisco repeatedly until it reaches 100 degrees."))
            elif choice == "4":
                print("\n--- Running Test 4: Unknown City Tool Error ---")
                print(agent("What is the temperature in Atlantis?"))
            else:
                print(f"Invalid choice '{choice}'. Please enter a number between 1 and 4, or 'q' to quit.")

            print("\n📊 Check traces live at http://localhost:6006")
    finally:
        px.close_app()
        print("Tracing server closed.")
