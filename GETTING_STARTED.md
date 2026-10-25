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

### 5. View Observability & Self-Healing Traces

When `dummyAgent.py`, `self_healing_demo.py`, or `test_suite.py` is running, Arize Phoenix launches a local web UI:

- **Phoenix Dashboard**: [http://localhost:6006](http://localhost:6006)

Here you can inspect:
- Root spans (`Agent_Workflow`): marked `Status: OK` with attribute `agent.self_healed: true` upon remediation.
- Self-Healing Spans:
  - `SelfHealing_Observation`: Captures anomaly error modes, tool inputs, and stagnation patterns.
  - `SelfHealing_Analysis`: Root-cause diagnosis and strategy routing.
  - `SelfHealing_Remediation`: Records the applied recovery tactic, latency, and recovered outputs.
- Step-by-step LLM completion spans (`LLM_step_1`, `LLM_step_2`, etc.)
- Tool execution latency and payloads (`tool_fetch_api_data`, `tool_save_summery_file`, `tool_get_temperature`)

---

### 6. Run the Self-Healing Interactive Demo

To run side-by-side comparisons (Baseline Failure vs. Self-Healed Success) or run the automated benchmark matrix:

```bash
python self_healing_demo.py
```

Demo Options:
- **`1-4`**: Side-by-side comparison for any scenario:
  1. *HTTP 404 API Error* -> Healed via `ApiFallbackStrategy`
  2. *Silent Template Hallucination (`{{...}}`)* -> Healed via `TemplateHydrationStrategy`
  3. *Infinite Loop & Deadlock* -> Healed via `LoopBreakerStrategy`
  4. *Unknown Domain Entity (`Atlantis`)* -> Healed via `EntityResolverStrategy`
- **`A`**: Automated benchmark suite running all 4 scenarios in both modes and displaying a comparison table.
- **`Q`**: Quit and stop the tracing server.

---

### 7. Run the Failure Mode Test Suite

To run tests with dynamic toggle between Self-Healing mode and Baseline failure mode:

```bash
python test_suite.py
```

- Press **`m`** at any time to toggle Self-Healing mode ON/OFF.
- Select **`1-4`** to execute the corresponding scenario.

---

## 🛠️ Self-Healing Architecture & Rules

The agent operates under an automated closed-loop healing framework:

1. **Observe**: `HealthObserver` intercepts malformed JSON, unparsed mustache templates, tool exceptions/404s, and cyclic loop stagnation.
2. **Analyze**: `DiagnosticAnalyzer` diagnoses the root cause, selects the targeted strategy, and logs an OTel diagnosis span.
3. **Remediate**: `RemediationExecutor` resolves the issue using memory-aware template hydration, canonical URL fallback, fuzzy entity matching, or loop-breaker intervention.
4. **Trace**: Arize Phoenix records the healing lifecycle and updates the root workflow status from `ERROR` to `SELF_HEALED`.

---

## 📁 Project Structure

```
Dummy-Agent/
│
├── self_healing/                 # Modular Self-Healing Framework
│   ├── __init__.py               # Public API exports
│   ├── observer.py               # Anomaly, loop, and error event observer
│   ├── analyzer.py               # Diagnostic classifier & strategy selector
│   ├── remediation.py            # Closed-loop remediation executor
│   ├── telemetry.py              # OpenTelemetry spans (Observation, Analysis, Remediation)
│   ├── llm_fallback.py           # Resilient LLM simulation & infrastructure fallback
│   └── strategies/               # Recovery strategies
│       ├── template_hydrator.py  # Resolves {{variable}} from prior context
│       ├── api_fallback.py       # Reroutes 404s to canonical endpoints & fallbacks
│       ├── loop_breaker.py       # Detects cycles & injects loop-breaking guidance
│       ├── entity_resolver.py    # Fuzzy domain entity matcher
│       └── json_repair.py        # Malformed JSON auto-repair
│
├── dummyAgent.py                 # Main agent loop with self_healing toggle & Phoenix tracing
├── self_healing_demo.py          # Interactive side-by-side demonstration runner
├── test_suite.py                 # Interactive test suite with healing mode toggle
├── logger.py                     # Structured JSON logger for agent & tool monitoring
├── requirements.txt              # Python dependencies
├── .env.local                    # Environment variables (API tokens)
├── post_summary.md               # Sample output file written by the agent
└── GETTING_STARTED.md            # Setup & usage documentation
```
