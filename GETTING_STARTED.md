# Getting Started with Dummy-Agent

An autonomous AI agent with tool execution capabilities, strict sequential task chaining, template hallucination detection, and live observability with OpenTelemetry & Arize Phoenix.

---

## 🌟 Overview

The **Dummy-Agent** executes multi-turn autonomous workflows with strict rule enforcement:
1. **Sequential Tool Execution**: Fetches data from remote APIs (`fetch_api_data`), reasons & summarizes findings, and writes them to disk (`save_the_file`).
2. **Silent Template & Format Validation**: Detects and rejects unparsed hallucinated placeholders (such as `{{variable}}`) in tool arguments.
3. **Infinite Loop Protection**: Enforces turn limits (`max_turns`) to prevent unbounded LLM loops.
4. **Live Tracing & Observability**: Powered by OpenTelemetry and Arize Phoenix (`http://localhost:6006`) for span tracking, latency measurement, and failure mode analysis.

---

## 📋 Prerequisites

- **Python**: Version 3.9 or higher
- **Virtual Environment**: Recommended (`venv` or Conda)
- **API Access**: Hugging Face token or OpenAI API key

---

## 🚀 Quickstart Guide

### 1. Activate the Virtual Environment

On Windows (PowerShell):
```powershell
.\dummyAgent\Scripts\activate
```

On Linux/macOS:
```bash
source dummyAgent/bin/activate
```

---

### 2. Install Dependencies

Install all required packages from `requirements.txt`:
```bash
pip install -r requirements.txt
```

---

### 3. Configure Environment Variables

Create or edit the `.env.local` file in the project root:

```ini
# Hugging Face API Key
HUGGING_FACE_API=your_hugging_face_token_here

# (Optional) OpenAI API Key if switching inference backend
OPENAI_API_KEY=your_openai_api_key_here
```

---

### 4. Run the Agent

To execute the autonomous agent with the default fetch-summarize-save workflow:

```bash
python dummyAgent.py
```

**Default Workflow Run**:
- The agent calls `fetch_api_data` for `https://jsonplaceholder.typicode.com/posts/1`.
- It processes and summarizes the response.
- It calls `save_the_file` to write the summary to `post_summary.md`.
- It displays the final confirmation message and outputs live trace links.

---

### 5. View Observability Traces

When `dummyAgent.py` or `test_suite.py` is running, Arize Phoenix launches a local web UI:

- **Phoenix Dashboard**: [http://localhost:6006](http://localhost:6006)

Here you can inspect:
- Root spans (`Agent_Workflow`)
- Step-by-step LLM completion spans (`LLM_step_1`, `LLM_step_2`, etc.)
- Tool execution latency and payloads (`tool_fetch_api_data`, `tool_save_summery_file`)
- Failure modes (`ToolExecutionError`, `SilentValidationError`, `InfiniteLoopError`)

---

### 6. Run the Failure Mode Test Suite

To test error handling, placeholder rejection, and loop limits:

```bash
python test_suite.py
```

Select a test mode from the prompt:
- **`1` - Tool Execution Failure**: Simulates a 404 REST API endpoint call.
- **`2` - Silent Template Error**: Tests detection and blocking of `{{fetch_api_data.output.body}}` template syntax.
- **`3` - Infinite Loop Error**: Tests `max_turns` limit safeguard.
- **`4` - Unknown City Tool Error**: Tests validation inside domain-specific tools.

---

## 🛠️ Agent Rules & Workflow

The agent operates under strict operational guidelines:

```
1. Always solve the user request step-by-step using the provided tools.
2. Sequential Workflow:
   - Step 1: Call 'fetch_api_data' with the target URL to obtain raw JSON data.
   - Step 2: Once the tool returns data, summarize the key findings in your reasoning.
   - Step 3: Call 'save_the_file' with the summarized text and target filename.
   - Step 4: When information is complete, provide a final concise confirmation message to the user.
3. CRITICAL: Never generate placeholder templates like '{{variable}}' in tool arguments. All tool arguments must be concrete values.
4. Do not call 'save_the_file' before 'fetch_api_data' returns data.
5. If a tool returns an error, examine the error message and attempt an alternative or report the issue clearly.
```

---

## 📁 Project Structure

```
Dummy-Agent/
│
├── dummyAgent.py          # Main agent loop, tool definitions & Phoenix tracing
├── logger.py              # Structured JSON logger for agent & tool monitoring
├── test_suite.py          # Interactive test suite for failure modes
├── requirements.txt       # Python dependencies
├── .env.local             # Environment variables (API tokens)
├── post_summary.md        # Sample output file written by the agent
└── GETTING_STARTED.md     # Setup & usage documentation
```
