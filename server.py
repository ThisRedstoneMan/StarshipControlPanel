import asyncio
import json
from pathlib import Path
from main import build_mission_state
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI()

# Keep track of connected clients so we can broadcast to all of them
connected_clients: set[WebSocket] = set()


@app.websocket("/ws/state")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_clients.add(websocket)
    try:
        while True:
            # We don't expect messages from the client, but this keeps
            # the connection alive and lets us detect disconnects.
            await websocket.receive_text()
    except WebSocketDisconnect:
        connected_clients.discard(websocket)


async def broadcast_loop():
    """Runs forever in the background, pushing state to every client."""
    while True:
        state = build_mission_state()
        message = json.dumps(state)
        dead_clients = set()
        for client in connected_clients:
            try:
                await client.send_text(message)
            except Exception:
                dead_clients.add(client)
        connected_clients.difference_update(dead_clients)
        await asyncio.sleep(0.5)  # matches your original updateInterval


@app.on_event("startup")
async def start_background_loop():
    asyncio.create_task(broadcast_loop())


@app.get("/", response_class=HTMLResponse)
async def index():
    html_path = Path(__file__).parent / "web" / "index.html"
    return html_path.read_text()


if __name__ == "__main__":
    import uvicorn
    # 0.0.0.0 = listen on all network interfaces, so your phone can reach it
    uvicorn.run(app, host="0.0.0.0", port=8000)
