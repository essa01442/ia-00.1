import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import asyncio

from .core.brain import Brain
from .core.toolbox import Toolbox
from .core.logger import log

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
        log.info("Client disconnected.")
    except Exception as e:
        log.error(f"An unexpected error occurred in the main loop: {e}", exc_info=True)
        try:
            await websocket.send_json({"type": "error", "message": f"An unexpected server error occurred: {e}"})
        except Exception:
            pass # Websocket might be closed
    finally:
        log.info("Closing connection and resources.")
        await toolbox.disconnect()
        if not websocket.client_state == 'DISCONNECTED':
             await websocket.close()

@app.get("/")
async def read_root():
    return {"message": "Agent backend is running."}
