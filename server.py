import asyncio
import json
import threading
from pathlib import Path
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

# Import our shared state and background thread runner
from main import current_state, telemetry_update_loop

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
        # Simply read the latest data from the background thread's dictionary
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
    # 1. Start the FastAPI WebSocket broadcasting task
    asyncio.create_task(broadcast_loop())
    
    # 2. Start your main update loop in a separate, non-blocking background thread!
    threading.Thread(target=telemetry_update_loop, daemon=True).start()

@app.get("/", response_class=HTMLResponse)
async def index():
    html_path = Path(__file__).parent / "web" / "index.html"
    return html_path.read_text()

if __name__ == "__main__":
    import uvicorn
    # 0.0.0.0 listens on your local network, allowing your phone to connect
    uvicorn.run(app, host="0.0.0.0", port=8000)