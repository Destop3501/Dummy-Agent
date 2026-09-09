import sys
import os
from pathlib import Path

# Ensure UTF-8 output encoding on Windows consoles
if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

from dotenv import load_dotenv
import json
import time
from huggingface_hub import InferenceClient
from pydantic import BaseModel, Field
import requests

import phoenix as px
from phoenix.otel import register
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

LOGGER_DIRECTION =  Path(__file__).resolve().parent.parent / "Logger"

if str(LOGGER_DIRECTION) not in sys.path:
    sys.path.append(str(LOGGER_DIRECTION))

from logger import logger

session = px.launch_app(use_temp_dir=False)

# Register Phoenix as OpenTelemetry Tracer Provider
tracer_provider = register(project_name="default", auto_instrument=True)

tracer = trace.get_tracer("customer_agent_tracer")

load_dotenv(dotenv_path=".env.local")
HF_TOKEN = os.getenv("HUGGING_FACE_API")

client = InferenceClient(
    api_key=HF_TOKEN,
    model="Qwen/Qwen2.5-72B-Instruct"
)

# response = client.chat.completions.create(
#     messages=[
#         {"role": "user", "content": "Are you sentient?"}
#     ],
#     max_tokens=500
# ) 
@tracer.start_as_current_span("tool_get_temperature")
def get_temperature(city: str):
    """
    Gets the temperature of a city.
    """
    span = trace.get_current_span()
    span.set_attribute("tool.name", "fetch_api_data")
    span.set_attribute("tool.input.city", city)
    
    if city.lower() == "san francisco":
        span.set_attribute("tool.output", "75")
        span.set_status(Status(StatusCode.OK))
        return "75"
    if city.lower() == "paris":
        span.set_attribute("tool.output", "78")
        span.set_status(Status(StatusCode.OK))
        return "78"
    if city.lower() == "tokyo":
        span.set_attribute("tool.output", "80")
        span.set_status(Status(StatusCode.OK))
        return "80"

    error_message = f"Unknown city: {city}"
    span.set_attribute("failure.mode", "ToolExcicutionError")
    span.set_status(Status(StatusCode.ERROR))
    return error_message

# get_temperature_tool_schema = {
#     "type" : "function",
#     "function": {
#         "name": "get_temperature",
#         "description": "Get the temperature of a city",
#         "parameters": {
#             "type" : "object",
#             "properties": {
#                 "city": {
#                     "type": "string",
#                     "description": "The city that need to get temperature"
#                 }
#             },
#             "required": ["city"]
#         }
#     }
# }

class GetTemperatureArgs(BaseModel):
    city: str = Field(..., description="The city want to get the temperatre")

temperature = {
    "type": "function",
    "function": {
        "name": "get_temperature",
        "description": "Get the temperature of a city",
        "parameters": GetTemperatureArgs.model_json_schema()
    }
}

# response1 = client.chat.completions.create(
#     messages=[
#         {"role": "user", "content": "what is the temperature in San Francisco today?"}
#     ],
#     tools=[temperature],
#     max_tokens=500,
#     tool_choice="auto"
# )

class FetchAPIArgs(BaseModel):
    url: str = Field(..., description="The API url to fetch JSON data from")

@tracer.start_as_current_span("tool_fetch_api_data")
def fetch_api_data(url: str) -> str:
    """
        Fetch data to this using url
    """
    span = trace.get_current_span()
    span.set_attribute("tool.name", "fetch_api_data")
    span.set_attribute("tool.input.url", url)
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = json.dumps(response.json())

        span.set_attribute("tool.output", data[:200])
        span.set_status(Status(StatusCode.OK))

        return data
    except Exception as e:
        span.record_exception(e)
        span.set_attribute("failure.mode", "ToolExecutionError")
        span.set_status(Status(StatusCode.ERROR, str(e)))

        return f"Error: {str(e)}"

fetchapi = {
    "type": "function",
    "function": {
        "name": "fetch_api_data",
        "description": "Fetch data from a REST API endpoint URL",
        "parameters": FetchAPIArgs.model_json_schema()
    }
}

class SaveFileArgs(BaseModel):
    data: str = Field(..., description="Sumerice content to write in a file")
    file: str = Field("summary.md", description="The File that saved the summery")

@tracer.start_as_current_span("tool_save_summery_file")
def save_the_file(data: str, file: str= "summary.md") -> str:
    """
        Sumerize and save in a file
    """
    span = trace.get_current_span()
    span.set_attribute("tool.name", "save_summery_file")
    span.set_attribute("tool.input.data", data[:200])
    span.set_attribute("tool.input.filename", file)

    try:
        with open(file, "w", encoding="utf-8") as f:
            f.write(data)

        result = "successfully saved the summery"
        span.set_attribute("tool.output", result)
        span.set_status(Status(StatusCode.OK))

        return result
    except Exception as e:
        span.record_exception(e)
        span.set_attribute("failure.mode", "ToolExecutionError")
        span.set_status(Status(StatusCode.ERROR, str(e)))

        return f"Error saving file {str(e)}"

savefile = {
    "type": "function",
    "function": {
        "name": "save_the_file",
        "description": "sumerise the data and save in the file",
        "parameters": SaveFileArgs.model_json_schema()
    }
}

class Agent:
    def __init__(self, client: InferenceClient, system: str = "", tools: list = None, max_turns: int = 5) -> None:
        self.client = client
        self.system = system
        self.messages: list = []
        self.tools = tools if tools is not None else []
        self.max_turns = max_turns
        if self.system:
            self.messages.append(
                {
                    "role": "system", 
                    "content": self.system
                } 
            )
    
    def __call__(self, message: str = ""):
        with tracer.start_as_current_span("Agent_Workflow") as root_span:
            root_span.set_attribute("agent.user_message", message)

            if message:
                self.messages.append(
                    {
                        "role": "user",
                        "content": message
                    }
                )
            final_assistence_response = self.execute()

            if final_assistence_response:
                self.messages.append(
                    {
                        "role": "assistant",
                        "content": final_assistence_response
                    }
                )
                root_span.set_attribute("agent.final_response", final_assistence_response)

            return final_assistence_response

    def execute(self):
        step_count = 0
        while True:
            step_count += 1

            if step_count > self.max_turns:
                with tracer.start_as_current_span("Failure_Infinite_Loop") as loop_span:
                    err_msg = f"Agent exceeded maximum allowed turns limit of {self.max_turns}"
                    loop_span.set_attribute("failure.mode", "InfiniteLoopError")
                    loop_span.set_attribute("turns_count", step_count)
                    loop_span.set_status(Status(StatusCode.ERROR, err_msg))
                    logger.error(err_msg, extra={"status": "error", "failure_mode": "InfiniteLoopError"})
                    return f"Error: {err_msg}"

            with tracer.start_as_current_span(f"LLM_step_{step_count}") as LLM_span:
                LLM_span.set_attribute("LLM.Message_Count", len(self.messages))

                completion = self.client.chat.completions.create(
                    messages=self.messages,
                    tools=self.tools,
                    tool_choice="auto"
                )
                
                response_message = completion.choices[0].message

                if response_message.tool_calls:
                    self.messages.append(response_message)
                    LLM_span.set_attribute("LLM.tools_calls_requested", len(response_message.tool_calls))

                    tool_outputs = []
                    for tool_call in response_message.tool_calls:
                        function_name = tool_call.function.name
                        raw_arguments = tool_call.function.arguments
                        try:
                            function_args = json.loads(raw_arguments)
                        except json.JSONDecodeError as json_err:
                            with tracer.start_as_current_span("Failure_FormatError") as format_span:
                                format_span.record_exception(json_err)
                                format_span.set_attribute("failure.mode", "FormatError")
                                format_span.set_attribute("raw_arguments", raw_arguments)
                                format_span.set_status(Status(StatusCode.ERROR, "Malformed JSON arguments returned by LLM"))
                                
                                logger.error("JSON decode error", extra={"raw_args": raw_arguments})

                            tool_outputs.append({
                                "tool_call_id": tool_call.id,
                                "role": "tool",
                                "name": function_name,
                                "content": f"Error: Arguments must be valid JSON string. Provided: {raw_arguments}"
                            })
                            continue

                        if "{{" in raw_arguments or "}}" in raw_arguments:
                            with tracer.start_as_current_span("Failure_SilentTemplateError") as template_span:
                                template_err = "LLM generated unparsed placeholder variables like '{{...}}' instead of concrete data"
                                template_span.set_attribute("failure.mode", "SilentValidationError")
                                template_span.set_attribute("invalid_arguments", raw_arguments)
                                template_span.set_status(Status(StatusCode.ERROR, template_err))
                                
                                logger.warning("Template hallucination detected", extra={"args": raw_arguments})

                            tool_outputs.append({
                                "tool_call_id": tool_call.id,
                                "role": "tool",
                                "name": function_name,
                                "content": f"Error: Silent template validation error. Placeholder syntax '{{...}}' is not permitted in tool arguments: {raw_arguments}"
                            })
                            continue

                        if function_name in globals() and callable(globals()[function_name]):
                            function_to_call = globals()[function_name]

                            start_time = time.time()

                            try:
                                execute_output = function_to_call(**function_args)
                                tool_output_contain = str(execute_output)

                                latency_ms = int((time.time() - start_time) * 1000)

                                print("\n Logger \n\n")
                                
                                logger.info(
                                    "Tool Execution Complete",
                                    extra = {
                                        "tool_name": function_name,
                                        "latency_ms": latency_ms,
                                        "status": "success",
                                        "output_preview": tool_output_contain[:100]
                                    }
                                )
                            
                            except Exception as e:
                                latency_ms = int((time.time() - start_time) * 1000)
                                tool_output_contain = f"Error: {str(e)}"

                                with tracer.start_as_current_span("Failure_ToolExecution") as tool_err_span:
                                    tool_err_span.record_exception(e)
                                    tool_err_span.set_attribute("failure.mode", "ToolExecutionError")
                                    tool_err_span.set_status(Status(StatusCode.ERROR, str(e)))

                                print("\n Logger \n\n")

                                logger.error(
                                    "Tool execution failed", 
                                    extra={
                                        "tool_name": function_name,
                                        "latency_ms": latency_ms,
                                        "status": "error",
                                        "error_message": str(e)
                                    }
                                )

                        tool_outputs.append(
                            {
                                "tool_call_id": tool_call.id,
                                "role": "tool",
                                "name": function_name,
                                "content": tool_output_contain
                            }
                        )

                    self.messages.extend(tool_outputs)

                else:
                    LLM_span.set_attribute("LLM.final_text_generated", True)

                    return response_message.content

system_prompt = (
    "You are an autonomous AI agent. ALWAYS perform tasks sequentially:\n"
    "1. First, call 'fetch_api_data' to retrieve the raw data.\n"
    "2. Wait for the API result to return.\n"
    "3. Summarize the returned content in your context.\n"
    "4. Finally, call 'save_the_file' with the summarized text.\n"
    "NEVER call 'save_the_file' in parallel with 'fetch_api_data',"
    "calculate the temparture,"
)

tools = [temperature, fetchapi, savefile]

agent = Agent(client, system_prompt, tools, max_turns=5)

if __name__ == "__main__":
    try:
        print(agent("Fetch data from https://jsonplaceholder.typicode.com/posts/1, summarize its key content, and save the summary to 'post_summary.md'."))

        print("\n📊 View execution traces live in your browser at: http://localhost:6006")
        input("Press Enter to stop tracing server...")

        print()
        print(agent.messages)
    finally:
        px.close_app()