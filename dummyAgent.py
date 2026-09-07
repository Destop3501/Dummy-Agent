import os
import getpass
from dotenv import load_dotenv
import json
from huggingface_hub import InferenceClient
from pydantic import BaseModel, Field
import requests
import time

import sys
from pathlib import Path

LOGGER_DIRECTION =  Path(__file__).resolve().parent.parent / "Logger"

if str(LOGGER_DIRECTION) not in sys.path:
    sys.path.append(str(LOGGER_DIRECTION))

from logger import logger

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

def get_temperature(city: str):
    """
    Gets the temperature of a city.
    """
    if city.lower() == "san francisco":
        return "75"
    if city.lower() == "paris":
        return "78"
    if city.lower() == "tokyo":
        return "80"
    return "Unknown"

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

def fetch_api_data(url: str) -> str:
    """
        Fetch data to this using url
    """
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        return json.dumps(response.json())
    except Exception as e:
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

def save_the_file(data: str, file: str= "summary.md") -> str:
    """
        Sumerize and save in a file
    """

    try:
        with open(file, "w", encoding="utf-8") as f:
            f.write(data)
        return "sucessfuly saved the summery"
    except Exception as e:
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
    def __init__(self, client: InferenceClient, system: str = "", tools: list = None) -> None:
        self.client = client
        self.system = system
        self.messages: list = []
        self.tools = tools if tools is not None else []
        if self.system:
            self.messages.append(
                {
                    "role": "system", 
                    "content": self.system
                } 
            )
    
    def __call__(self, message: str = ""):
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

        return final_assistence_response

    def execute(self):
        while True:
            completion = self.client.chat.completions.create(
                messages=self.messages,
                tools=self.tools,
                tool_choice="auto"
            )
            
            response_message = completion.choices[0].message

            if response_message.tool_calls:
                self.messages.append(response_message)

                tool_outputs = []
                for tool_call in response_message.tool_calls:
                    function_name = tool_call.function.name
                    function_args = json.loads(tool_call.function.arguments)

                    if function_name in globals() and callable(globals()[function_name]):
                        function_to_call = globals()[function_name]

                        start_time = time.time()

                        try:
                            execute_output = function_to_call(**function_args)
                            tool_output_contain = str(execute_output)

                            latency_ms = int((time.time() - start_time) * 1000)
                            
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
                return response_message.content

client = InferenceClient(
    api_key=HF_TOKEN,
    model="Qwen/Qwen2.5-72B-Instruct"
)

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

agent = Agent(client, system_prompt, tools)

print(agent("Fetch data from https://jsonplaceholder.typicode.com/posts/1, summarize its key content, and save the summary to 'post_summary.md'."))

print(agent.messages)