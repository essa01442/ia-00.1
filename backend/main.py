import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import ollama
import os
import json
import asyncio
import tomli
from playwright.async_api import async_playwright, Playwright

# --- Configuration Loading ---
try:
    with open("config.toml", "rb") as f:
        config = tomli.load(f)
except FileNotFoundError:
    config = {}
    print("Warning: config.toml not found. Using default values.")

OLLAMA_HOST = config.get("llm", {}).get("host", "http://localhost:11434")
OLLAMA_MODEL = config.get("llm", {}).get("model", "llama3")
PROTECTED_FILES = config.get("security", {}).get("protected_files", [])

# --- The Toolbox ---
class Toolbox:
    def __init__(self):
        self.playwright: Playwright | None = None
        self.browser = None
        self.page = None

    async def _ensure_playwright(self):
        if self.playwright is None:
            self.playwright = await async_playwright().start()

    async def browser_attach(self, cdp_url: str):
        await self._ensure_playwright()
        try:
            self.browser = await self.playwright.chromium.connect_over_cdp(cdp_url)
            if self.browser.contexts() and self.browser.contexts()[0].pages:
                 self.page = self.browser.contexts()[0].pages[0]
            else:
                 self.page = await self.browser.new_page()
            return "Successfully attached to the browser."
        except Exception as e:
            return f"Error attaching to browser: {e}."

    async def browser_navigate(self, url: str):
        if not self.page: return "Error: Not attached to a browser."
        try:
            await self.page.goto(url)
            return f"Navigated to {url}."
        except Exception as e: return f"Error navigating: {e}"

    async def browser_click(self, selector: str):
        if not self.page: return "Error: Not attached to a browser."
        element = self.page.locator(selector).first
        if await element.get_attribute("type") == "password":
            return "PAUSE: Password field detected."
        try:
            await element.click()
            return f"Clicked on '{selector}'."
        except Exception as e: return f"Error clicking element: {e}"

    async def browser_type_text(self, selector: str, text: str):
        if not self.page: return "Error: Not attached to a browser."
        element = self.page.locator(selector).first
        if await element.get_attribute("type") == "password":
            return "PAUSE: Password field detected."
        try:
            await element.fill(text)
            return f"Typed text into '{selector}'."
        except Exception as e: return f"Error typing text: {e}"

    async def browser_type_and_submit(self, type_selector: str, text: str, submit_selector: str):
        type_result = await self.browser_type_text(type_selector, text)
        if "PAUSE" in type_result or "Error" in type_result: return type_result
        click_result = await self.browser_click(submit_selector)
        if "Error" in click_result: return f"Text typed, but submit failed: {click_result}"
        return "Successfully typed and submitted."

    async def browser_wait_for_response(self, selector: str, timeout: int = 30000):
        if not self.page: return "Error: Not attached to a browser."
        try:
            await self.page.wait_for_selector(selector, timeout=timeout)
            return f"Element '{selector}' appeared."
        except Exception as e: return f"Error waiting for '{selector}': {e}"

    async def browser_extract_text(self):
        if not self.page: return "Error: Not attached to a browser."
        try:
            return await self.page.content()
        except Exception as e: return f"Error extracting text: {e}"

    async def disconnect(self):
        if self.browser:
            await self.browser.close()
            self.browser = None
        if self.playwright:
            await self.playwright.stop()
            self.playwright = None

    def list_files(self, path: str = "."):
        if ".." in path or path.startswith("/"): return "Error: Access to parent or absolute directories is not allowed."
        try:
            return "\n".join(os.listdir(path))
        except Exception as e: return f"Error listing files: {e}"

    def read_file(self, path: str):
        if ".." in path or path.startswith("/"): return "Error: Access to parent or absolute directories is not allowed."
        try:
            with open(path, 'r') as f: return f.read()
        except Exception as e: return f"Error reading file: {e}"

    def write_file(self, path: str, content: str):
        if ".." in path or path.startswith("/"): return "Error: Access to parent or absolute directories is not allowed."
        if os.path.exists(path) and path in PROTECTED_FILES: return f"Error: Overwriting '{path}' is not allowed."
        try:
            with open(path, 'w') as f: f.write(content)
            return f"File '{path}' written successfully."
        except Exception as e: return f"Error writing file: {e}"

    def get_tools_json_schema(self):
        # In a real app, this would be more dynamic
        return {
            "list_files": { "description": "Lists files in a directory.", "params": {"path": {"type": "string"}}},
            "read_file": { "description": "Reads a file.", "params": {"path": {"type": "string"}}},
            "write_file": { "description": "Writes to a file.", "params": {"path": {"type": "string"}, "content": {"type": "string"}}},
            "browser_attach": { "description": "Attaches to a user's running browser via CDP endpoint.", "params": {"cdp_url": {"type": "string"}}},
            "browser_navigate": { "description": "Navigates to a URL.", "params": {"url": {"type": "string"}}},
            "browser_click": { "description": "Clicks an element on the page.", "params": {"selector": {"type": "string"}}},
            "browser_type_text": { "description": "Types text into an element.", "params": {"selector": {"type": "string"}, "text": {"type": "string"}}},
            "browser_type_and_submit": { "description": "Types text and clicks a submit button.", "params": {"type_selector": {"type": "string"}, "text": {"type": "string"}, "submit_selector": {"type": "string"}}},
            "browser_wait_for_response": { "description": "Waits for a specific element to appear on the page.", "params": {"selector": {"type": "string"}, "timeout": {"type": "integer", "description": "Timeout in milliseconds"}}},
            "browser_extract_text": { "description": "Extracts HTML content from the page.", "params": {}},
            "finish_task": { "description": "Call when the task is complete.", "params": {"reason": {"type": "string"}}}
        }

    async def execute_tool(self, tool_name: str, params: dict):
        tool_map = {
            "list_files": self.list_files, "read_file": self.read_file, "write_file": self.write_file,
            "browser_attach": self.browser_attach, "browser_navigate": self.browser_navigate,
            "browser_click": self.browser_click, "browser_type_text": self.browser_type_text,
            "browser_type_and_submit": self.browser_type_and_submit,
            "browser_wait_for_response": self.browser_wait_for_response,
            "browser_extract_text": self.browser_extract_text,
        }
        if tool_name not in tool_map: raise ValueError(f"Unknown tool: {tool_name}")
        tool_function = tool_map[tool_name]
        return await tool_function(**params) if asyncio.iscoroutinefunction(tool_function) else tool_function(**params)

# --- The Brain ---
class Brain:
    # (Same as before)
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

    def initialize_history(self, toolbox: Toolbox):
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

# --- FastAPI Application ---
app = FastAPI()

@app.websocket("/ws/execute_task")
async def execute_task_ws(websocket: WebSocket):
    await websocket.accept()
    brain = Brain()
    toolbox = Toolbox()
    brain.initialize_history(toolbox)

    try:
        while True:
            user_message = await websocket.receive_text()

            # Handle control messages
            if user_message == "stop":
                await websocket.send_json({"type": "status", "message": "Agent stopped by user."})
                break

            brain.add_user_message(user_message)

            last_result = None
            while True:
                next_step = await brain.step(last_result)
                await websocket.send_json(next_step)

                if "action" in next_step:
                    action = next_step["action"]
                    params = next_step.get("params", {})

                    if action == "finish_task":
                        break

                    try:
                        result = await toolbox.execute_tool(action, params)
                        last_result = str(result)
                        await websocket.send_json({"type": "action_result", "tool": action, "output": last_result})

                        if last_result.startswith("PAUSE:"):
                            await websocket.send_json({"type": "pause", "message": last_result})
                            resume_msg = await websocket.receive_text()
                            if resume_msg == "resume":
                                last_result = "User has handled the password field."
                                await websocket.send_json({"type": "status", "message": "Agent is resuming."})
                            else:
                                brain.add_user_message(resume_msg)
                                break

                    except Exception as e:
                        last_result = f"Error executing tool {action}: {e}"
                        await websocket.send_json({"type": "error", "message": last_result})
                else:
                    last_result = None

                try:
                    interrupt_message = await asyncio.wait_for(websocket.receive_text(), timeout=0.01)
                    brain.add_user_message(interrupt_message)
                    await websocket.send_json({"type": "status", "message": "Received new instruction, replanning..."})
                    break
                except asyncio.TimeoutError:
                    continue

    except WebSocketDisconnect:
        print("Client disconnected.")
    finally:
        await toolbox.disconnect()
        if not websocket.client_state == 'DISCONNECTED':
             await websocket.close()

@app.get("/")
async def read_root():
    return {"message": "Agent backend is running."}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
