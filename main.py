from libraries.countdownLib import getSignedSecondsFromT0, format_seconds_to_clock
import time
import json

spacexCountdownUrl = "https://content.spacex.com/cms-assets/future_missions.json"
flightID = "F343A80AAFA11416DBEA660C9ADB5728982363A1DB46756A4C4C86849048088B"
signed_seconds = getSignedSecondsFromT0(spacexCountdownUrl, flightID)
updateInterval = 0.5 #in seconds
running = True

MILESTONES_PATH = "./data/milestones.json"

def load_milestones():
    if MILESTONES_PATH.exists():
        with open(MILESTONES_PATH) as f:
            return json.load(f)
    return {}

def build_mission_state() -> dict:
    try:
        now = time.time()
        delta = now - signed_seconds  # negative before launch, positive after

        sign = "+" if delta >= 0 else "-"
        abs_delta = abs(delta)
        hh = int(abs_delta // 3600)
        mm = int((abs_delta % 3600) // 60)
        ss = int(abs_delta % 60)
        clock_str = f"T{sign} {hh:02d}:{mm:02d}:{ss:02d}"

        return {
            "ok": True,
            "clock": clock_str,
            "t_seconds": delta,
            "phase": "pre-launch" if delta < 0 else "post-launch",
            "milestones": load_milestones(),
            "server_time": now,
        }
    except Exception as e:
        return {"ok": False, "error": str(e), "server_time": time.time()}

def getCountdownClock():
    signedSeconds = getSignedSecondsFromT0(spacexCountdownUrl, flightID)
    if signedSeconds is not None:
        countdown_clock = format_seconds_to_clock(signedSeconds)
        return countdown_clock
    else:
        return "Error retrieving countdown clock."
    
#Main loop
# while running:
#     FormattedCountdownClock = getCountdownClock()
    
    
    
    
    
    
    
#     time.sleep(updateInterval)