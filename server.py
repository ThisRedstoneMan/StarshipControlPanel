import asyncio
import datetime
import hmac
import json
import os
import re
import sys
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from libraries.generalLib import print_colored

# ---------------------------------------------------------------------
# Console logging: everything this process prints - plain print()
# calls AND print_colored() calls (server.py's own debug-auth warning,
# plus anything main.py's background telemetry thread prints, since it
# all runs in-process) - is mirrored to a log file with a timestamp on
# every line.
#
# print_colored() ultimately calls print() too, so it's caught by the
# same stdout wrapper; the only extra thing done for it is stripping
# the ANSI color escape codes it embeds, so the log file stays plain,
# readable text while the console still shows it in color.
#
# The one thing deliberately left out of the file entirely is the
# periodic "Endpoint connection successes in the last 60s: N" line from
# main.py's print_network_stats() - it's still shown on the console,
# it's just noisy to keep re-reading in a log.
# ---------------------------------------------------------------------
LOG = Path(__file__).parent / "server.log"

_LOG_EXCLUDE_SNIPPET = "Endpoint connection successes in the last"
_ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*m")


class _TimestampedLogTee:
    """A stdout/stderr replacement that writes every line through
    unchanged (so the console looks the same as before) while also
    appending a timestamped copy of it to LOG, skipping any line that
    contains _LOG_EXCLUDE_SNIPPET."""

    def __init__(self, stream, log_path, exclude_snippet):
        self._stream = stream
        self._log_path = log_path
        self._exclude_snippet = exclude_snippet
        self._buffer = ""
        self._lock = threading.Lock()

    def write(self, message):
        self._stream.write(message)
        with self._lock:
            self._buffer += message
            while "\n" in self._buffer:
                line, self._buffer = self._buffer.split("\n", 1)
                self._log_line(line)
        return len(message)

    def _log_line(self, line):
        # Strip ANSI color codes (e.g. from print_colored()) before
        # deciding whether there's anything left to log, and before
        # writing - the console keeps the colored version, the log
        # file only ever gets plain text.
        clean_line = _ANSI_ESCAPE_RE.sub("", line)
        if not clean_line.strip():
            return
        if self._exclude_snippet in clean_line:
            return
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            with open(self._log_path, "a", encoding="utf-8") as log_file:
                log_file.write(f"[{timestamp}] {clean_line}\n")
        except OSError:
            # Never let a logging failure take down the server.
            pass

    def flush(self):
        self._stream.flush()

    def isatty(self):
        return getattr(self._stream, "isatty", lambda: False)()


sys.stdout = _TimestampedLogTee(sys.stdout, LOG, _LOG_EXCLUDE_SNIPPET)
sys.stderr = _TimestampedLogTee(sys.stderr, LOG, _LOG_EXCLUDE_SNIPPET)

# Import our shared state and background thread runner
from main import (
    current_state,
    telemetry_update_loop,
    debug_simulate_shift,
    debug_set_gradual_hold,
    debug_set_time,
    debug_advance_countdown,
    debug_toggle_weather,
    debug_toggle_pad_clear,
    debug_toggle_road_closure_close,
    debug_toggle_road_closure_far,
    debug_toggle_tank_farm_chilldown,
    debug_toggle_go_for_prop_load,
    debug_toggle_flight_director_go,
    debug_clear_override,
)

connected_clients: set[WebSocket] = set()

# ---------------------------------------------------------------------
# Debug auth: a single shared password gates the debug endpoints. Devices
# that supply the correct password get their IP added to an in-memory
# whitelist — nothing is written to disk, so the whitelist resets whenever
# the server restarts and every device has to re-authenticate.
#
# This is intentionally simple (IP-based, in-RAM, one shared password) and
# matches the README's existing "local network only" assumption. It is
# NOT meant to survive being exposed to the open internet: IPs can be
# spoofed or shared behind NAT/a proxy, and the password travels in
# plaintext unless you put this behind HTTPS yourself.
# ---------------------------------------------------------------------
DEBUG_PASSWORD = os.environ.get("STARSHIP_DEBUG_PASSWORD", "coolPassword")
if DEBUG_PASSWORD == "coolPassword":
    print_colored(
        ""
        "[debug-auth] WARNING: using the default debug password. Set STARSHIP_DEBUG_PASSWORD to something private before sharing this on your LAN."
    , {'red': (0, 20)}, new_line=True)

whitelisted_ips: set[str] = set()

# Basic brute-force guard: after too many wrong guesses from one IP,
# lock that IP out of /debug/auth for a while. Also in-RAM only.
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_SECONDS = 30
_failed_attempts: dict[str, int] = {}
_locked_until: dict[str, float] = {}


class DebugAuthRequest(BaseModel):
    password: str


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def require_whitelisted(request: Request) -> None:
    """FastAPI dependency: reject any debug route call from a device that
    hasn't successfully authenticated via /debug/auth."""
    if _client_ip(request) not in whitelisted_ips:
        raise HTTPException(
            status_code=403,
            detail="Not authorized. Enable Debug tools and enter the password first.",
        )

@asynccontextmanager
async def lifespan(app: FastAPI):
    broadcast_task = asyncio.create_task(broadcast_loop())
    threading.Thread(target=telemetry_update_loop, daemon=True).start()
    try:
        yield
    finally:
        broadcast_task.cancel()
        try:
            await broadcast_task
        except asyncio.CancelledError:
            pass

app = FastAPI(lifespan=lifespan)

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

# ---------------------------------------------------------------------
# Debug auth route: NOT gated by require_whitelisted (that would be a
# lockout loop — you need this route to get onto the whitelist).
# ---------------------------------------------------------------------
@app.post("/debug/auth")
async def debug_auth(body: DebugAuthRequest, request: Request):
    ip = _client_ip(request)

    locked_until = _locked_until.get(ip)
    if locked_until and time.time() < locked_until:
        remaining = int(locked_until - time.time())
        raise HTTPException(
            status_code=429,
            detail=f"Too many attempts. Try again in {remaining}s.",
        )

    if hmac.compare_digest(body.password, DEBUG_PASSWORD):
        whitelisted_ips.add(ip)
        _failed_attempts.pop(ip, None)
        _locked_until.pop(ip, None)
        return {"ok": True}

    _failed_attempts[ip] = _failed_attempts.get(ip, 0) + 1
    if _failed_attempts[ip] >= MAX_FAILED_ATTEMPTS:
        _locked_until[ip] = time.time() + LOCKOUT_SECONDS
        _failed_attempts[ip] = 0
        raise HTTPException(
            status_code=429,
            detail=f"Too many attempts. Try again in {LOCKOUT_SECONDS}s.",
        )

    raise HTTPException(status_code=401, detail="Incorrect password.")

# ---------------------------------------------------------------------
# Debug-only routes: let the phone/browser trigger a fake hold or delay
# to test detection + the banner + history, without waiting on a real
# SpaceX schedule change. Not meant to survive into a "real" deployment
# open to the public internet — this is for your local network only.
#
# Every route below requires the caller's IP to already be on the
# whitelist (see require_whitelisted / /debug/auth above). Anyone who
# hasn't entered the correct password gets a 403 on every one of these.
# ---------------------------------------------------------------------
@app.post("/debug/simulate")
async def debug_simulate(delta_seconds: float, _: None = Depends(require_whitelisted)):
    return debug_simulate_shift(delta_seconds)

@app.post("/debug/set-time")
async def debug_set_time_route(signed_seconds: float, _: None = Depends(require_whitelisted)):
    return debug_set_time(signed_seconds)

@app.post("/debug/advance")
async def debug_advance(seconds: float, _: None = Depends(require_whitelisted)):
    return debug_advance_countdown(seconds)

@app.post("/debug/toggle-weather")
async def debug_toggle_weather_route(_: None = Depends(require_whitelisted)):
    return debug_toggle_weather()

@app.post("/debug/toggle-pad-clear")
async def debug_toggle_pad_clear_route(_: None = Depends(require_whitelisted)):
    return debug_toggle_pad_clear()

@app.post("/debug/toggle-road-closure-close")
async def debug_toggle_road_closure_close_route(_: None = Depends(require_whitelisted)):
    return debug_toggle_road_closure_close()

@app.post("/debug/toggle-road-closure-far")
async def debug_toggle_road_closure_far_route(_: None = Depends(require_whitelisted)):
    return debug_toggle_road_closure_far()

@app.post("/debug/toggle-tank-farm-chilldown")
async def debug_toggle_tank_farm_chilldown_route(_: None = Depends(require_whitelisted)):
    return debug_toggle_tank_farm_chilldown()

@app.post("/debug/toggle-prop-load")
async def debug_toggle_prop_load_route(_: None = Depends(require_whitelisted)):
    return debug_toggle_go_for_prop_load()

@app.post("/debug/toggle-flight-director-go")
async def debug_toggle_flight_director_go_route(_: None = Depends(require_whitelisted)):
    return debug_toggle_flight_director_go()

@app.post("/debug/clear")
async def debug_clear(_: None = Depends(require_whitelisted)):
    return debug_clear_override()

@app.post("/debug/gradual-hold")
async def debug_gradual_hold(enabled: bool, _: None = Depends(require_whitelisted)):
    return debug_set_gradual_hold(enabled)

# Keep this mount last: the API and WebSocket routes above take priority,
# while the browser can load index.html, timeline.js, and future web assets.
WEB_DIRECTORY = Path(__file__).parent / "web"
app.mount("/", StaticFiles(directory=WEB_DIRECTORY, html=True), name="web")

if __name__ == "__main__":
    import uvicorn
    # 0.0.0.0 listens on your local network, allowing your phone to connect
    uvicorn.run(app, host="0.0.0.0", port=8000)