def format_seconds_to_clock(signed_seconds):
        prefix = "T- " if signed_seconds < 0 else "T+ "
        abs_secs = abs(signed_seconds)
        hours = abs_secs // 3600
        minutes = (abs_secs % 3600) // 60
        seconds = abs_secs % 60
        return f"{prefix}{hours:02d} : {minutes:02d} : {seconds:02d}"


def format_duration(seconds):
    """Formats a plain (unsigned-style) duration like '+02:15' or '-01:03:40',
    used for describing how far a hold/delay shifted T-0 by."""
    sign = "+" if seconds >= 0 else "-"
    abs_secs = abs(int(seconds))
    hours = abs_secs // 3600
    minutes = (abs_secs % 3600) // 60
    secs = abs_secs % 60
    if hours:
        return f"{sign}{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{sign}{minutes:02d}:{secs:02d}"


def classify_timestamp_change(previous_ts, new_ts, hold_threshold=600):
    """
    Classify a change in the target launch timestamp between two polls
    of the SpaceX countdown API.

    - previous_ts / new_ts: unix timestamps, or None if not known yet.
    - hold_threshold: shifts of this many seconds or fewer are treated as
      a "hold" (a short recycle within the same attempt, e.g. holding at
      T-40s and resuming a few minutes later). Anything bigger is a
      "delay" (pushed to a materially different time, e.g. scrubbed to
      the next day).

    Returns None if nothing meaningfully changed, otherwise a dict:
        {
          "type": "hold" | "delay",
          "delta_seconds": int,       # positive = T-0 pushed later
          "previous_timestamp": ...,
          "new_timestamp": ...,
        }
    """
    if previous_ts is None or new_ts is None:
        return None
    delta = int(new_ts - previous_ts)
    if delta == 0:
        return None

    kind = "hold" if abs(delta) <= hold_threshold else "delay"
    return {
        "type": kind,
        "delta_seconds": delta,
        "previous_timestamp": previous_ts,
        "new_timestamp": new_ts,
    }

def getLaunchTimestamp(url, flightID):
    import requests
    import json
    from datetime import datetime, timezone

    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        
        # Find the flight with the given flightID
        flight_data = data.get(flightID)
        
        if not flight_data:
            raise ValueError(f"Flight ID {flightID} not found in the data.")
        
        # Extract the launch time (assuming it's in Unix timestamp format)
        launch_time_timestamp = flight_data.get("PrimaryLaunchDate", {}).get("Seconds")
        if not launch_time_timestamp:
            raise ValueError(f"Launch time not found for Flight ID {flightID}.")
        
        return launch_time_timestamp
    
    except requests.RequestException as e:
        print(f"Error fetching data from {url}: {e}")
        return None
    except ValueError as ve:
        print(ve)
        return None     

def getSignedSeconds(launchTimeStamp):
    import time
    from datetime import datetime, timezone
    launch_time = datetime.fromtimestamp(launchTimeStamp, tz=timezone.utc)
    current_time = datetime.now(timezone.utc)
        
    # Calculate signed seconds
    signed_seconds = int((current_time - launch_time).total_seconds())
    return signed_seconds