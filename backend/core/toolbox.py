import os
import asyncio
from playwright.async_api import async_playwright, Playwright

from .logger import log
import tomli

# --- Configuration Loading ---
try:
    with open("config.toml", "rb") as f:
        config = tomli.load(f)
except FileNotFoundError:
    config = {}
    log.warning("config.toml not found in toolbox. Using default values for security.")
PROTECTED_FILES = config.get("security", {}).get("protected_files", [])


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
