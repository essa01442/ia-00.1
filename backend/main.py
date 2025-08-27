import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import asyncio

from .core.brain import Brain
from .core.toolbox import Toolbox
from .core.logger import log

# --- Helper Functions for WebSocket Logic ---

async def handle_tool_result(result: str, brain: Brain, websocket: WebSocket) -> str:
    """Handles the result of a tool execution, including the pause/resume logic."""
    last_result = str(result)
    await websocket.send_json({"type": "action_result", "output": last_result})

    if last_result.startswith("PAUSE:"):
        await websocket.send_json({"type": "pause", "message": last_result})
        resume_msg = await websocket.receive_text()  # Wait for user to resume
        if resume_msg == "resume":
            last_result = "User has handled the password field."
            await websocket.send_json({"type": "status", "message": "Agent is resuming."})
        else:
            # If the user sent something other than "resume", treat it as a new instruction
            brain.add_user_message(resume_msg)
            last_result = "INTERRUPTED" # Special signal to break the inner loop

    return last_result

async def run_agent_inner_loop(brain: Brain, toolbox: Toolbox, websocket: WebSocket):
    """Runs the agent's think-act cycle until it finishes or is interrupted."""
    last_result = None
    while True:
        # Check for user interruption before the agent thinks
        try:
            interrupt_message = await asyncio.wait_for(websocket.receive_text(), timeout=0.01)
            brain.add_user_message(interrupt_message)
            await websocket.send_json({"type": "status", "message": "Received new instruction, replanning..."})
            break # Break inner loop to re-plan based on new message
        except asyncio.TimeoutError:
            pass # No interruption, continue

        # Agent thinks of the next step
        next_step = await brain.step(last_result)
        await websocket.send_json(next_step)

        if "action" in next_step:
            action = next_step["action"]
            params = next_step.get("params", {})

            if action == "finish_task":
                log.info(f"Task finished with reason: {params.get('reason')}")
                break # Break inner loop, wait for next user message

            try:
                result = await toolbox.execute_tool(action, params)
                last_result = await handle_tool_result(result, brain, websocket)
                if last_result == "INTERRUPTED":
                    break # Break inner loop to re-plan

            except Exception as e:
                log.error(f"Error executing tool {action}: {e}", exc_info=True)
                last_result = f"Error executing tool {action}: {e}"
                await websocket.send_json({"type": "error", "message": last_result})
        else:
            # It was a thought, so no result to process
            last_result = None

# --- FastAPI Application ---

app = FastAPI()

@app.websocket("/ws/execute_task")
async def execute_task_ws(websocket: WebSocket):
    """Main WebSocket endpoint for handling the agent session."""
    await websocket.accept()
    log.info("WebSocket connection accepted.")

    brain = Brain()
    toolbox = Toolbox()
    brain.initialize_history(toolbox)

    try:
        while True:
            # Wait for a user message to start or continue the conversation
            user_message = await websocket.receive_text()
            log.info(f"Received message from user: {user_message}")

            if user_message == "stop":
                await websocket.send_json({"type": "status", "message": "Agent stopped by user."})
                break

            brain.add_user_message(user_message)

            # Start the agent's execution loop for this turn
            await run_agent_inner_loop(brain, toolbox, websocket)

    except WebSocketDisconnect:
        log.info("Client disconnected.")
    except Exception as e:
        log.error(f"An unexpected error occurred in the main WebSocket handler: {e}", exc_info=True)
        try:
            await websocket.send_json({"type": "error", "message": f"An unexpected server error occurred."})
        except Exception:
            pass # Websocket might already be closed
    finally:
        log.info("Closing connection and cleaning up resources.")
        await toolbox.disconnect()
        if websocket.client_state != 'DISCONNECTED':
             await websocket.close()

@app.get("/")
async def read_root():
    return {"message": "Agent backend is running."}
