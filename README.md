# Interactive Smart Agent

This project is a Python-based interactive smart agent that can understand and execute tasks given by a user. It features a "Brain" powered by a local Large Language Model (LLM) via Ollama, a "Toolbox" for interacting with the digital world (file system and web browser), and a real-time web interface that visualizes the agent's thoughts and actions.

## Core Concepts

-   **The Brain**: The decision-making core that uses an LLM to create plans and choose tools. It's designed to be private and fast by leveraging local models.
-   **The Toolbox**: Gives the Brain its capabilities. It includes tools for file system operations (read, write, list) and browser automation (navigate, click, extract text) using Playwright.
-   **The Interactive Interface**: A web-based GUI that provides a live stream of the agent's inner workings. The user can watch the agent think and act in real-time and has an "Emergency Stop" button to halt execution at any moment.
-   **Security Guardrails**: The agent is built with safety in mind. It has built-in protections to prevent it from overwriting critical files, accessing sensitive directories, or interacting with password fields on websites.

## Project Structure

```
/
|-- backend/
|   |-- main.py           # FastAPI backend, WebSocket logic, Brain, Toolbox
|-- frontend/
|   |-- index.html        # Main HTML file for the UI
|   |-- style.css         # CSS for the user interface
|   |-- script.js         # JavaScript for frontend logic and WebSocket communication
|-- config.toml           # Configuration file for the agent
|-- pyproject.toml        # Python project dependencies
|-- README.md             # This file
```

## Setup and Installation

### 1. Prerequisites

-   **Python 3.9+**: Make sure you have a modern version of Python installed.
-   **Ollama**: You need to have Ollama installed and running to serve the local LLM. You can download it from [https://ollama.com/](https://ollama.com/).
-   **Pull an LLM Model**: Once Ollama is running, pull a model for the agent to use. The default is `llama3`.
    ```bash
    ollama pull llama3
    ```

### 2. Install Dependencies

The project uses Poetry for dependency management, but you can install the required packages using `pip`.

```bash
# It is recommended to use a virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies from pyproject.toml
pip install fastapi uvicorn "uvicorn[standard]" python-dotenv ollama playwright tomli
```

### 3. Install Browser Binaries

The agent uses Playwright for browser automation, which requires browser binaries to be installed. After installing the Python packages, run the following command:

```bash
playwright install
```
If you are on Linux and encounter issues, you may need to install system dependencies first:
```bash
sudo playwright install-deps
```

## How to Run

### 1. Configure the Agent

All settings are in `config.toml`. You can change the LLM model, Ollama host, and security policies in this file.

### 2. Start the Backend Server

Navigate to the project's root directory and run the following command:

```bash
python backend/main.py
```

The server will start on `http://localhost:8000`.

### 3. Open the Frontend

Open the `frontend/index.html` file in your web browser. You can usually do this by double-clicking the file or using your browser's "Open File" dialog.

### 4. Use the Agent

1.  Type a task into the input box (e.g., "Read the README.md file and tell me what this project is about.").
2.  Click the "Start Agent" button.
3.  Watch the agent's log as it thinks and executes the task.
4.  Click the "Stop Agent" button at any time to halt the process.