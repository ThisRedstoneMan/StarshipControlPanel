import asyncio
import json
import threading
from pathlib import Path
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

# Import our shared state and background thread runner
from main import (
    current_state,
    telemetry_update_loop,
    debug_simulate_shift,
    debug_clear_override,
)

app = FastAPI()
connected_clients: set[WebSocket] = set()

@app.websocket("/ws/state")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_clients.add(websocket)
    try:
        while True:
            # Keeps the socket connection alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        connected_clients.discard(websocket)

async def broadcast_loop():
    """Reads the shared state and pushes it to all phone/browser clients."""
    while True:
        message = json.dumps(current_state)
        dead_clients = set()
        for client in connected_clients:
            try:
                await client.send_text(message)
            except Exception:
                dead_clients.add(client)
        connected_clients.difference_update(dead_clients)
        await asyncio.sleep(0.5)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(broadcast_loop())
    threading.Thread(target=telemetry_update_loop, daemon=True).start()

@app.get("/", response_class=HTMLResponse)
async def index():
    html_path = Path(__file__).parent / "web" / "index.html"
    return html_path.read_text(encoding="utf-8")

# ---------------------------------------------------------------------
# Debug-only routes: let the phone/browser trigger a fake hold or delay
# to test detection + the banner + history, without waiting on a real
# SpaceX schedule change. Not meant to survive into a "real" deployment
# open to the public internet — this is for your local network only.
# ---------------------------------------------------------------------
@app.post("/debug/simulate")
async def debug_simulate(delta_seconds: float):
    return debug_simulate_shift(delta_seconds)

@app.post("/debug/clear")
async def debug_clear():
    return debug_clear_override()

if __name__ == "__main__":
    import uvicorn
    # 0.0.0.0 listens on your local network, allowing your phone to connect
    uvicorn.run(app, host="0.0.0.0", port=8000)