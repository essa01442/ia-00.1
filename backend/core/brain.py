import ollama
import json
import tomli
from .logger import log

# --- Configuration Loading ---
try:
    with open("config.toml", "rb") as f:
        config = tomli.load(f)
except FileNotFoundError:
    config = {}
    log.warning("config.toml not found. Using default values.")

OLLAMA_HOST = config.get("llm", {}).get("host", "http://localhost:11434")
OLLAMA_MODEL = config.get("llm", {}).get("model", "llama3")


class Brain:
    def __init__(self, model: str = OLLAMA_MODEL):
        self.model = model
        self.client = ollama.AsyncClient(host=OLLAMA_HOST)
        self.history = []

    def _get_system_prompt(self, tools_schema):
        return f"""
You are a helpful AI assistant. Your goal is to solve the user's task by thinking step-by-step and using tools.
You must always output your response in a valid JSON format.
When the user gives you a new instruction, you must stop your current plan and address the new instruction.
Available tools:
{json.dumps(tools_schema, indent=2)}
"""

    def initialize_history(self, toolbox):
        tools_schema = toolbox.get_tools_json_schema()
        system_prompt = self._get_system_prompt(tools_schema)
        self.history = [{"role": "system", "content": system_prompt}]

    def add_user_message(self, message: str):
        self.history.append({"role": "user", "content": message})

    async def step(self, last_action_result: str = None):
        if last_action_result:
            self.history.append({"role": "user", "content": f"Tool output: {last_action_result}"})
        response = await self.client.chat(model=self.model, messages=self.history, options={"temperature": 0.1}, format="json")
        response_content = response['message']['content']
        self.history.append({"role": "assistant", "content": response_content})
        try:
            return json.loads(response_content)
        except json.JSONDecodeError:
            return {"thought": response_content}
