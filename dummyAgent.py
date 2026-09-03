import os
import getpass
from dotenv import load_dotenv
# pyrefly: ignore [missing-import]
from huggingface_hub import InferenceClient
from pydantic import BaseModel, Field

load_dotenv(dotenv_path=".env.local")

HF_TOKEN = os.getenv("HUGGING_FACE_API")

client =  InferenceClient(
    api_key = HF_TOKEN,
    model = "Qwen/Qwen2.5-72B-Instruct"
)

response = client.chat.completions.create(
    messages = [
        {"role": "user", "content": "Are you sentient?"}
    ],
    max_tokens=500
) 

print(response.__dict__) 
print()
print(response.choices[0].message.content)
print()
print(response.choices[0].message.reasoning_content)

def get_temperature(city:str):
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
    tool_choice = "auto"
)


print(response1.__dict__) 
print()
print(response1.choices[0].message.content)
print()
print(response1.choices[0].message.reasoning_content)
print()
print(response1.choices[0].message.tool_calls[0].function.__dict__)

    