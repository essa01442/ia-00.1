import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
import ollama
import os
import subprocess
import json
import asyncio
import tomli
from playwright.async_api import async_playwright

# --- Configuration Loading ---
try:
    with open("config.toml", "rb") as f:
        config = tomli.load(f)
except FileNotFoundError:
    print("Error: config.toml not found. Please create it.")
    exit(1)
except tomli.TOMLDecodeError:
    print("Error: Could not decode config.toml. Please check its syntax.")
    exit(1)

OLLAMA_HOST = config.get("llm", {}).get("host", "http://localhost:11434")
OLLAMA_MODEL = config.get("llm", {}).get("model", "llama3")
PROTECTED_FILES = config.get("security", {}).get("protected_files", [])

# --- The Toolbox ---
class Toolbox:
    """Holds a collection of tools the agent can use."""
    def __init__(self):
        self.browser = None
        self.page = None

    async def browser_start(self, url: str):
        """Starts a browser, creates a new page, and navigates to the URL."""
        try:
            p = await async_playwright().start()
            self.browser = await p.chromium.launch()
            self.page = await self.browser.new_page()
            await self.page.goto(url)
            return f"Browser started and navigated to {url}."
        except Exception as e:
            return f"Error starting browser: {e}"

    async def browser_navigate(self, url: str):
        """Navigates the current page to a new URL."""
        if not self.page:
            return "Error: Browser not started. Use browser_start first."
        try:
            await self.page.goto(url)
            return f"Navigated to {url}."
        except Exception as e:
            return f"Error navigating: {e}"

    async def browser_click(self, selector: str):
        """Clicks on an element specified by a CSS selector."""
        if not self.page:
            return "Error: Browser not started."
        element = self.page.locator(selector).first
        element_type = await element.get_attribute("type")
        if element_type == "password":
            return "Error: Interaction with password fields is not allowed for security reasons."
        try:
            await element.click()
            return f"Clicked on element with selector '{selector}'."
        except Exception as e:
            return f"Error clicking element: {e}"

    async def browser_extract_text(self):
        """Extracts all visible text from the current page."""
        if not self.page:
            return "Error: Browser not started."
        try:
            return await self.page.content()
        except Exception as e:
            return f"Error extracting text: {e}"

    async def browser_close(self):
        """Closes the browser."""
        if not self.browser:
            return "Browser not running."
        try:
            await self.browser.close()
            self.browser = None
            self.page = None
            return "Browser closed."
        except Exception as e:
            return f"Error closing browser: {e}"

    def list_files(self, path: str = "."):
        """Lists files in a given directory."""
        if ".." in path or path.startswith("/"):
            return "Error: Access to parent or absolute directories is not allowed."
        try:
            return "\n".join(os.listdir(path))
        except Exception as e:
            return f"Error listing files: {e}"

    def read_file(self, path: str):
        """Reads the content of a file."""
        if ".." in path or path.startswith("/"):
            return "Error: Access to parent or absolute directories is not allowed."
        try:
            with open(path, 'r') as f:
                return f.read()
        except Exception as e:
            return f"Error reading file: {e}"

    def write_file(self, path: str, content: str):
        """Writes content to a file."""
        if ".." in path or path.startswith("/"):
            return "Error: Access to parent or absolute directories is not allowed."
        if os.path.exists(path) and path in PROTECTED_FILES:
            return f"Error: Overwriting the file '{path}' is not allowed for security reasons."
        try:
            with open(path, 'w') as f:
                f.write(content)
            return f"File '{path}' written successfully."
        except Exception as e:
            return f"Error writing file: {e}"

    def get_tools_json_schema(self):
        """Returns a JSON schema of available tools for the LLM."""
        return {
            "list_files": { "description": "Lists files in a directory.", "params": {"path": {"type": "string"}}},
            "read_file": { "description": "Reads a file.", "params": {"path": {"type": "string"}}},
            "write_file": { "description": "Writes to a file.", "params": {"path": {"type": "string"}, "content": {"type": "string"}}},
            "browser_start": { "description": "Starts a browser and navigates to a URL.", "params": {"url": {"type": "string"}}},
            "browser_navigate": { "description": "Navigates to a URL.", "params": {"url": {"type": "string"}}},
            "browser_click": { "description": "Clicks an element on the page.", "params": {"selector": {"type": "string"}}},
            "browser_extract_text": { "description": "Extracts text from the page.", "params": {}},
            "browser_close": { "description": "Closes the browser.", "params": {}},
            "finish_task": { "description": "Call when the task is complete.", "params": {"reason": {"type": "string"}}}
        }

    async def execute_tool(self, tool_name: str, params: dict):
        """Executes a given tool with parameters."""
        if tool_name == "list_files": return self.list_files(**params)
        elif tool_name == "read_file": return self.read_file(**params)
        elif tool_name == "write_file": return self.write_file(**params)
        elif tool_name == "browser_start": return await self.browser_start(**params)
        elif tool_name == "browser_navigate": return await self.browser_navigate(**params)
        elif tool_name == "browser_click": return await self.browser_click(**params)
        elif tool_name == "browser_extract_text": return await self.browser_extract_text()
        elif tool_name == "browser_close": return await self.browser_close()
        else: raise ValueError(f"Unknown tool: {tool_name}")

# --- The Brain ---
class Brain:
    """The decision-making core of the agent."""
    def __init__(self, model: str = OLLAMA_MODEL):
        self.model = model
        self.client = ollama.AsyncClient(host=OLLAMA_HOST)
        self.history = []

    def _get_system_prompt(self, tools_schema):
        return f"""
You are a helpful AI assistant that can use tools to complete tasks.
Your goal is to solve the user's task by thinking step-by-step and using the available tools.
You must always output your response in a valid JSON format. Choose one of two formats:
1. For expressing a thought: {{"thought": "Your thought process here..."}}
2. For choosing a tool to use: {{"action": "tool_name", "params": {{"arg1": "value1"}}}}
Here are the tools you have available:
{json.dumps(tools_schema, indent=2)}
Begin by thinking about the user's task. Then, use the tools to execute your plan.
If you believe the task is complete, use the "finish_task" action.
"""

    async def think(self, user_task: str, toolbox: Toolbox):
        """Initial thinking step."""
        tools_schema = toolbox.get_tools_json_schema()
        system_prompt = self._get_system_prompt(tools_schema)
        self.history = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Here is my task:\n{user_task}"}
        ]

    async def step(self, last_action_result: str = None):
        """Generates the next step."""
        if last_action_result:
            self.history.append({"role": "user", "content": f"Tool output: {last_action_result}"})

        response = await self.client.chat(model=self.model, messages=self.history, options={"temperature": 0.1}, format="json")
        response_content = response['message']['content']
        self.history.append({"role": "assistant", "content": response_content})

        try:
            return json.loads(response_content)
        except json.JSONDecodeError:
            return {"thought": response_content}

# --- FastAPI Application ---
app = FastAPI()

@app.websocket("/ws/execute_task")
async def execute_task_ws(websocket: WebSocket):
    await websocket.accept()
    task = await websocket.receive_text()

    brain = Brain()
    toolbox = Toolbox()
    await brain.think(task, toolbox)

    try:
        last_result = None
        while True:
            try:
                message = await asyncio.wait_for(websocket.receive_text(), timeout=0.01)
                if message == "stop":
                    await websocket.send_json({"type": "status", "message": "Agent stopped by user."})
                    break
            except asyncio.TimeoutError:
                pass

            next_step = await brain.step(last_result)
            await websocket.send_json(next_step)

            if "action" in next_step:
                action = next_step["action"]
                params = next_step.get("params", {})

                if action == "finish_task":
                    await websocket.send_json({"type": "status", "message": "Task completed."})
                    break

                try:
                    result = await toolbox.execute_tool(action, params)
                    last_result = str(result)
                    await websocket.send_json({"type": "action_result", "tool": action, "output": last_result})
                except Exception as e:
                    last_result = f"Error executing tool {action}: {e}"
                    await websocket.send_json({"type": "error", "message": last_result})
            else:
                last_result = None

    except WebSocketDisconnect:
        print("Client disconnected.")
    except Exception as e:
        error_message = f"An unexpected error occurred: {e}"
        print(error_message)
        try:
            await websocket.send_json({"type": "error", "message": error_message})
        except Exception:
            pass
    finally:
        if toolbox.browser:
            await toolbox.browser_close()
        if not websocket.client_state == 'DISCONNECTED':
             await websocket.close()

@app.get("/")
async def read_root():
    return {"message": "Agent backend is running."}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
