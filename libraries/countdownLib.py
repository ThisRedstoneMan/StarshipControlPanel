launch_site_timezones = {
    "Pad 1, Starbase": "America/Chicago",
    "Pad 2, Starbase": "America/Chicago",
    "SLC-40, Florida": "America/New_York",
    "LC-39A, Florida": "America/New_York",
    "SLC-4E, California": "America/Los_Angeles",
}

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


def _parse_site_local_datetime(date_str, time_strn, launch_site):
    from datetime import datetime
    from zoneinfo import ZoneInfo

    if not date_str or not time_strn:
        return None

    tz_name = launch_site_timezones.get(launch_site)
    if not tz_name:
        return None

    launch_tz = ZoneInfo(tz_name)
    try:
        local_dt = datetime.strptime(f"{date_str} {time_strn}", "%Y-%m-%d %H:%M:%S")
    except ValueError:
        try:
            local_dt = datetime.fromisoformat(f"{date_str}T{time_strn}")
        except ValueError:
            return None

    return local_dt.replace(tzinfo=launch_tz).timestamp()


def getLaunchDetails(url, flightID):
    """Fetch launch details including the launch window bounds from SpaceX's mission payload."""
    import requests

    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()

        mission = next((m for m in data if m.get("correlationId") == flightID), None)
        if mission is None:
            raise ValueError(f"Flight ID {flightID} not found in the data.")

        override = mission.get("override") or {}
        launch_date = override.get("windowOpenDate") or mission.get("launchDate")
        launch_time = override.get("windowOpenTime") or mission.get("launchTime")
        launch_timestamp = None
        if launch_date and launch_time:
            launch_timestamp = _parse_site_local_datetime(launch_date, launch_time, mission.get("launchSite"))

        window_start = _parse_site_local_datetime(override.get("windowOpenDate"), override.get("windowOpenTime"), mission.get("launchSite"))
        window_end = _parse_site_local_datetime(override.get("windowCloseDate"), override.get("windowCloseTime"), mission.get("launchSite"))

        if launch_timestamp is None and window_start is not None:
            launch_timestamp = window_start
        if launch_timestamp is None and window_end is not None:
            launch_timestamp = window_end

        return {
            "launch_timestamp": launch_timestamp,
            "window_start": window_start,
            "window_end": window_end,
        }

    except requests.RequestException as e:
        print(f"Error fetching data from {url}: {e}")
        return {"launch_timestamp": None, "window_start": None, "window_end": None}
    except ValueError as ve:
        print(ve)
        return {"launch_timestamp": None, "window_start": None, "window_end": None}
    except Exception as e:
        print(f"Unexpected error parsing launch data: {e}")
        return {"launch_timestamp": None, "window_start": None, "window_end": None}


def getLaunchTimestamp(url, flightID):
    """
    Fetches the target launch time for a mission from SpaceX's
    launches-page-tiles endpoint.

    The old future_missions.json endpoint returned a dict keyed by flight
    ID with a ready-made Unix timestamp. This endpoint instead returns a
    flat LIST of missions, each identified by "correlationId" (lowercase
    "d" — different casing than the old API's "correlationID"), and gives
    a separate date + time string rather than a Unix timestamp.

    Within a mission, "override.windowOpenDate"/"windowOpenTime" is
    SpaceX's current best estimate of T-0 once a launch has a live
    countdown window (this is what shifts if they scrub or reschedule).
    Before that, or if there's no override yet, we fall back to the
    mission's base "launchDate"/"launchTime".

    Unlike the old endpoint (raw UTC Unix timestamps), these date/time
    strings are in the LAUNCH SITE'S LOCAL time, not UTC — confirmed by a
    5-hour discrepancy that matches Starbase, Texas being on Central time
    (UTC-5 during CDT). We use zoneinfo rather than a fixed offset so this
    keeps working correctly across the DST boundary (CDT/UTC-5 in summer,
    CST/UTC-6 in winter) instead of silently drifting by an hour twice a
    year. If you point this at a mission from a different launch site
    (Florida/California), update LAUNCH_SITE_TIMEZONE accordingly — the
    API does not appear to indicate per-mission timezone itself.
    """
    details = getLaunchDetails(url, flightID)
    return details.get("launch_timestamp")


def getSignedSeconds(launchTimeStamp):
    import time
    from datetime import datetime, timezone
    launch_time = datetime.fromtimestamp(launchTimeStamp, tz=timezone.utc)
    current_time = datetime.now(timezone.utc)
        
    # Calculate signed seconds
    signed_seconds = int((current_time - launch_time).total_seconds())
    return signed_seconds