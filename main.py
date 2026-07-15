import time
import json
import threading
from pathlib import Path
from libraries.countdownLib import (
    getLaunchTimestamp,
    getSignedSeconds,
    classify_timestamp_change,
    format_duration,
)

spacexCountdownUrl = "https://content.spacex.com/cms-assets/future_missions.json"
flightID = "F343A80AAFA11416DBEA660C9ADB5728982363A1DB46756A4C4C86849048088B"
fetchInterval = 0.5  # in seconds
updateInterval = 0.1  # in seconds
signed_seconds = 0
launch_timestamp = 0
running = True
MILESTONES_PATH = Path("./data/milestones.json")

# How many past hold/delay events to keep for display (most recent first).
MAX_EVENT_HISTORY = 10

# Debug override: when active, the displayed countdown is driven by
# debug_override["launch_timestamp"] instead of the real SpaceX one.
# fetch_clock_async keeps polling the real API in the background so it
# can resume cleanly from wherever the real countdown actually is once
# the override is cleared.
debug_override = {"active": False, "launch_timestamp": None}

# A hold that is reported as a series of small T-0 slips is represented as
# one event, whose duration grows until the timestamp stops moving.
active_hold = None
gradual_hold = {"active": False, "thread": None}


def fetch_clock_async():
    global signed_seconds, launch_timestamp
    real_previous_ts = None

    while running:
        new_real_ts = getLaunchTimestamp(spacexCountdownUrl, flightID)

        if new_real_ts is not None:
            # Only treat real API changes as hold/delay events while we're
            # NOT in the middle of a debug simulation, so a test doesn't
            # get immediately overwritten/confused by a real poll.
            if not debug_override["active"]:
                event = classify_timestamp_change(real_previous_ts, new_real_ts)
                handle_timestamp_event(event)
            real_previous_ts = new_real_ts

        if debug_override["active"]:
            effective_ts = debug_override["launch_timestamp"]
        else:
            effective_ts = new_real_ts if new_real_ts is not None else real_previous_ts

        if effective_ts is not None:
            launch_timestamp = effective_ts
            signed_seconds = getSignedSeconds(effective_ts)

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
    "telemetry": {},
    # Nominal until a poll detects the SpaceX target timestamp moving.
    "countdown_status": {
        "type": "nominal",       # "nominal" | "hold" | "delay"
        "message": None,
        "delta_seconds": 0,
        "detected_at": None,
        "simulated": False,
    },
    "countdown_events": [],      # history, most recent first
}


def record_countdown_event(event, simulated=False):
    """Turns a classify_timestamp_change() result into a human-readable
    status + history entry, and stores both in current_state."""
    global current_state

    if event["type"] == "hold":
        if event["delta_seconds"] > 0:
            message = f"Hold detected — T-0 slipped {format_duration(event['delta_seconds'])}"
        else:
            message = f"Countdown resumed early — T-0 moved up {format_duration(-event['delta_seconds'])}"
    else:  # "delay"
        if event["delta_seconds"] > 0:
            message = f"Launch delayed — T-0 pushed back {format_duration(event['delta_seconds'])}"
        else:
            message = f"Launch moved earlier by {format_duration(-event['delta_seconds'])}"

    if simulated:
        message = f"[TEST] {message}"

    entry = {
        "type": event["type"],
        "message": message,
        "delta_seconds": event["delta_seconds"],
        "detected_at": time.time(),
        "simulated": simulated,
    }

    current_state["countdown_status"] = entry
    current_state["countdown_events"] = (
        [entry] + current_state["countdown_events"]
    )[:MAX_EVENT_HISTORY]

    print(f"[countdown] {message}")


def handle_timestamp_event(event, simulated=False):
    """Record timestamp changes, merging consecutive small positive slips.

    A launch provider can express a hold by moving T-0 forward one second at
    a time.  Updating the same history entry avoids treating that as hundreds
    of separate holds.
    """
    global active_hold

    if event is None:
        active_hold = None
        return

    is_small_positive_hold = event["type"] == "hold" and event["delta_seconds"] > 0
    if not is_small_positive_hold:
        active_hold = None
        record_countdown_event(event, simulated=simulated)
        return

    if active_hold is None:
        record_countdown_event(event, simulated=simulated)
        active_hold = {
            "entry": current_state["countdown_status"],
            "delta_seconds": event["delta_seconds"],
            "simulated": simulated,
        }
        return

    # Keep the current banner and the most-recent history entry in sync;
    # they refer to the same dictionary.
    active_hold["delta_seconds"] += event["delta_seconds"]
    total = active_hold["delta_seconds"]
    prefix = "[TEST] " if active_hold["simulated"] else ""
    active_hold["entry"].update({
        "message": f"{prefix}Hold detected - T-0 slipped {format_duration(total)}",
        "delta_seconds": total,
        "detected_at": time.time(),
    })


def _gradual_hold_loop():
    """Advance the debug T-0 by one second per real second while enabled."""
    while gradual_hold["active"]:
        time.sleep(1)
        if not gradual_hold["active"]:
            break

        baseline = debug_override["launch_timestamp"]
        if baseline is None:
            continue
        new_timestamp = baseline + 1
        event = classify_timestamp_change(baseline, new_timestamp)
        debug_override["launch_timestamp"] = new_timestamp
        handle_timestamp_event(event, simulated=True)


def debug_set_gradual_hold(enabled):
    """Start or stop a debug hold which slips T-0 by one second per second."""
    if enabled:
        baseline = debug_override["launch_timestamp"] if debug_override["active"] else launch_timestamp
        if not baseline:
            return {"ok": False, "error": "No launch timestamp known yet - wait for the first real fetch."}

        debug_override["active"] = True
        debug_override["launch_timestamp"] = baseline
        if not gradual_hold["active"]:
            gradual_hold["active"] = True
            gradual_hold["thread"] = threading.Thread(target=_gradual_hold_loop, daemon=True)
            gradual_hold["thread"].start()
        return {"ok": True, "enabled": True}

    gradual_hold["active"] = False
    debug_clear_override()
    return {"ok": True, "enabled": False}


def debug_simulate_shift(delta_seconds):
    """
    Artificially shifts T-0 by delta_seconds, for testing hold/delay
    detection and the UI banner without waiting for a real SpaceX update.
    Positive delta = countdown slips later (hold/delay). Negative = pulled
    earlier. Runs through the exact same classify/record path a real
    change would, so it's a genuine end-to-end test of the pipeline.
    """
    baseline = debug_override["launch_timestamp"] if debug_override["active"] else launch_timestamp
    if not baseline:
        return {"ok": False, "error": "No launch timestamp known yet — wait for the first real fetch."}

    new_ts = baseline + delta_seconds
    event = classify_timestamp_change(baseline, new_ts)
    handle_timestamp_event(event, simulated=True)

    debug_override["active"] = True
    debug_override["launch_timestamp"] = new_ts
    return {"ok": True, "new_timestamp": new_ts}


def debug_clear_override():
    """Stops the simulation; fetch_clock_async resumes from whatever the
    real countdown actually is (it never stopped tracking it)."""
    global active_hold
    gradual_hold["active"] = False
    active_hold = None
    debug_override["active"] = False
    debug_override["launch_timestamp"] = None
    return {"ok": True}


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
    global launch_timestamp
    launch_timestamp = getLaunchTimestamp(spacexCountdownUrl, flightID)
    if launch_timestamp is not None:
        signed_seconds = getSignedSeconds(launch_timestamp)
    # If this first fetch fails, fetch_clock_async's own loop will pick
    # up a good timestamp shortly and signed_seconds will start updating.

    while True:
        if signed_seconds is not None:
            calculate_and_update_state(signed_seconds)
            
        
        
        time.sleep(updateInterval)
