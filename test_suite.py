import sys
import os

# Ensure UTF-8 output encoding on Windows consoles
if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

from dummyAgent import agent, px

if __name__ == "__main__":
    try:
        print("\n--- AGENT FAILURE MODE TEST SUITE ---")
        print("1. Tool Execution Failure (404 API)")
        print("2. Silent Template Error")
        print("3. Infinite Loop Error")
        print("4. Unknown City Tool Error")
        
        choice = input("Select test mode (1-4): ").strip()

        if choice == "1":
            print(agent("Fetch data from https://jsonplaceholder.typicode.com/nonexistent_page_404, summarize it, and save to 'fail.md'."))
        elif choice == "2":
            print(agent("Save the raw unparsed template string '{{fetch_api_data.output.body}}' into 'template.md' using save_the_file tool."))
        elif choice == "3":
            print(agent("Keep checking the temperature of San Francisco repeatedly until it reaches 100 degrees."))
        elif choice == "4":
            print(agent("What is the temperature in Atlantis?"))
        else:
            print("Invalid choice selected.")

        print("\n📊 Check traces live at http://localhost:6006")
        input("Press Enter to exit...")
    finally:
        px.close_app()
