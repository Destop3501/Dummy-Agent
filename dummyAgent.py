import os
import getpass
from dotenv import load_dotenv
import json
# pyrefly: ignore [missing-import]
from huggingface_hub import InferenceClient
from pydantic import BaseModel, Field

load_dotenv(dotenv_path=".env.local")

HF_TOKEN = os.getenv("HUGGING_FACE_API")

client = InferenceClient(
    api_key=HF_TOKEN,
    model="Qwen/Qwen2.5-72B-Instruct"
)

response = client.chat.completions.create(
    messages=[
        {"role": "user", "content": "Are you sentient?"}
    ],
    max_tokens=500
) 

print(response.__dict__) 
print()
print(response.choices[0].message.content)
print()
print(response.choices[0].message.reasoning_content)

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

schema = {
    "type": "function",
    "function": {
        "name": "get_temperature",
        "description": "Get the temperature of a city",
        "parameters": GetTemperatureArgs.model_json_schema()
    }
}
print(schema)

response1 = client.chat.completions.create(
    messages=[
        {"role": "user", "content": "what is the temperature in San Francisco today?"}
    ],
    tools=[schema],
    max_tokens=500,
    tool_choice="auto"
)

print(response1.__dict__) 
print()
print(response1.choices[0].message.content)
print()
print(response1.choices[0].message.reasoning_content)
print()
print(response1.choices[0].message.tool_calls[0].function.__dict__)

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
                        execute_output = function_to_call(**function_args)
                        tool_output_contain = str(execute_output)
                        print(f"Executing tool: {function_name} with args {function_args}, output {tool_output_contain[:500]}...")

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

system_prompt = "You are a helpful assistant."

tools = [schema]

agent = Agent(client, system_prompt, tools)

print(agent("what is the temperature of san Francisco?"))

print(agent.messages)