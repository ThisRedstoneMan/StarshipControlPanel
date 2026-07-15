import time
import json
import threading
from pathlib import Path
from libraries.countdownLib import getSignedSecondsFromT0

spacexCountdownUrl = "https://content.spacex.com/cms-assets/future_missions.json"
flightID = "F343A80AAFA11416DBEA660C9ADB5728982363A1DB46756A4C4C86849048088B"
fetchInterval = 0.5  # in seconds
updateInterval = 0.2  # in seconds
signed_seconds = 0
running = True
MILESTONES_PATH = Path("./data/milestones.json")

def fetch_clock_async():
    while running:
        global signed_seconds
        signed_seconds = getSignedSecondsFromT0(spacexCountdownUrl, flightID)
        time.sleep(fetchInterval)
        

def load_milestones():
    if MILESTONES_PATH.exists():
        with open(MILESTONES_PATH) as f:
            return json.load(f)
    return {}

milestones_data = load_milestones()

# This is our Shared State dictionary that server.py will read
current_state = {
    "ok": True,
    "clock": "T- 00:00:00",
    "t_seconds": 0,
    "phase": "pre-launch",
    "milestones": milestones_data,
    "server_time": time.time(),
    "telemetry": {}
}

def calculate_and_update_state(signed_seconds):
    """Calculates current clock/phase and updates the global dictionary."""
    global current_state
    try:
        delta = signed_seconds
        
        sign = "+" if delta >= 0 else "-"
        abs_delta = abs(delta)
        hh = int(abs_delta // 3600)
        mm = int((abs_delta % 3600) // 60)
        ss = int(abs_delta % 60)
        clock_str = f"T{sign} {hh:02d}:{mm:02d}:{ss:02d}"

        current_state.update({
            "ok": True,
            "clock": clock_str,
            "t_seconds": delta,
            "phase": "pre-launch" if delta < 0 else "post-launch",
            "server_time": time.time(),
        })
    except Exception as e:
        current_state.update({
            "ok": False,
            "error": str(e),
            "server_time": time.time()
        })

thread = threading.Thread(target=fetch_clock_async)
thread.start()
def telemetry_update_loop():
    """This function will run continuously on a background thread."""
    print("Background telemetry loop started...")
    
    # Fetch the official T0 time once at startup
    global signed_seconds
    signed_seconds = getSignedSecondsFromT0(spacexCountdownUrl, flightID)
    
    while True:
        if signed_seconds is not None:
            calculate_and_update_state(signed_seconds)
            
        # -------------------------------------------------------------
        # FUTURE EXPANSION: Put your OCR screen-reading logic right here!
        # Read numbers -> current_state["telemetry"] = parsed_data
        # -------------------------------------------------------------
        
        time.sleep(updateInterval)