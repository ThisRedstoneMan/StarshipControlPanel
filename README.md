# Starship Control Panel

A lightweight, real-time Starship launch dashboard for a browser on your computer or local network. It follows the configured SpaceX mission countdown, displays a mission timeline, detects T-0 changes, and tracks the post-load hold-fuel budget.

## Features

- Live `T-` / `T+` clock, phase, and milestone timeline.
- Responsive browser interface that works for everyone connected to the same network.
- Elastic timeline spacing: dense launch events remain readable without wasting space on long coast phases.
- Automatic comparison of consecutive T-0 timestamps to identify holds, resumed countdowns, delays, and earlier launch times.
- Consecutive small T-0 slips are grouped into one growing hold event instead of flooding the event history.
- Post-load hold-fuel bar: after Ship Load Complete at T-2:10, a 15-minute hold budget is tracked and displayed.
- Debug controls for timeline scrubbing, server-side time jumps, simulated holds/delays, and a continuous one-second-per-second hold.

## Requirements

- Python 3.10 or later
- Internet access to retrieve the configured SpaceX mission record
- A modern browser

Install the Python dependencies:

```bash
python -m pip install fastapi "uvicorn[standard]" requests
```

## Run locally

From the repository root:

```bash
python server.py
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000) in a browser.

The server listens on `0.0.0.0`, so another device on the same network can use:

```text
http://YOUR-COMPUTER-LAN-IP:8000
```

For example, a phone might open `http://192.168.1.82:8000`. If the connection fails, allow Python through your firewall for private networks.

Stop the server with `Ctrl+C`.

## How it works

```text
SpaceX mission data
        |
        v
main.py: fetch T-0, calculate live clock, detect timestamp changes
        |
        v
shared current_state dictionary
        |
        v
server.py: FastAPI + WebSocket broadcast every 0.5 seconds
        |
        v
web/index.html + web/timeline.js: dashboard and timeline
```

`main.py` polls the configured SpaceX future-missions endpoint. Its Unix timestamp is compared against the current UTC time, so the countdown remains timezone-independent. The web server broadcasts the shared state over `/ws/state`; the browser smoothly estimates the time between messages for an animated marker.

## Hold and delay detection

Each successful poll compares the new T-0 timestamp with the previous one.

| T-0 change | Result |
| --- | --- |
| No change | No event |
| Change of 10 minutes or less | Hold / resumed countdown |
| Change greater than 10 minutes | Delay / major schedule move |

Positive changes move T-0 later; negative changes move it earlier. If a provider expresses a hold as a stream of small changes, the app updates one active hold entry with its accumulated duration.

## Hold-fuel budget

`data/milestones.json` places **Ship Load Complete** at T-2:10. From that point, the dashboard treats the vehicle as having a 15-minute hold-fuel allowance.

- A positive detected hold after load completion deducts from the remaining allowance.
- The bar is grey before T-2:10, then green, amber, or red as the remaining budget falls.
- Returning to before load completion or receiving a major delay resets the budget, representing a new propellant-loading attempt.

This is a visualization model for the dashboard, not an official operational rule or live vehicle telemetry.

## Configuration

Edit the values near the top of `main.py` to follow another mission or tune polling:

```python
spacexCountdownUrl = "https://content.spacex.com/cms-assets/future_missions.json"
flightID = "F343A80AAFA11416DBEA660C9ADB5728982363A1DB46756A4C4C86849048088B"
fetchInterval = 0.5
updateInterval = 0.1
```

`flightID` must be a key present in the mission-data response. The countdown uses the record's `PrimaryLaunchDate.Seconds` field.

### Milestones

Edit [data/milestones.json](data/milestones.json) to change the displayed timeline. Each item has a label and a signed offset in seconds relative to T-0:

```json
{
  "name": "Liftoff",
  "time": 0
}
```

Negative values are before launch; positive values are after launch. Keep entries in chronological order for the clearest timeline.

## Debug tools

Enable **Debug tools** in the top-right of the dashboard to reveal local testing controls.

- **Manual time override** previews a timeline time in the browser only.
- **Jump countdown here** commits the selected time to the server and resets the hold-fuel budget.
- **+30s hold**, **+5min hold**, and **+2hr delay** run simulated T-0 changes through the normal detector.
- **Continuous hold** advances T-0 by one second per real second, useful for testing the merged hold event and fuel bar.
- **Clear simulation** restores live mission data and resets test state.

The debug routes have no authentication. Keep this server on a trusted local network; do not expose it directly to the public internet.

## HTTP and WebSocket endpoints

| Endpoint | Purpose |
| --- | --- |
| `GET /` | Dashboard HTML and static assets |
| `WS /ws/state` | Live dashboard state |
| `POST /debug/set-time?signed_seconds=...` | Set a server-side debug countdown time |
| `POST /debug/simulate?delta_seconds=...` | Simulate a T-0 change |
| `POST /debug/gradual-hold?enabled=true` | Start/stop the continuous hold simulation |
| `POST /debug/clear` | Clear the debug override |

## Project structure

```text
.
+-- data/
|   +-- milestones.json       # Timeline events relative to T-0
+-- libraries/
|   +-- countdownLib.py       # Data fetching, timestamp and event helpers
|   +-- generalLib.py         # Cross-platform beep helper
+-- web/
|   +-- index.html            # Dashboard UI and debug controls
|   +-- timeline.js           # SVG elastic timeline renderer
+-- main.py                   # Countdown state, polling, hold/fuel logic
+-- server.py                 # FastAPI app, static files, WebSocket broadcast
```

## Limitations

- Countdown accuracy depends entirely on the SpaceX data endpoint and the selected mission record.
- A launch window or target may change without notice, and the endpoint may temporarily contain stale or incomplete data.
- Hold and fuel-budget behavior is an inference/visualization, not confirmed launch-provider telemetry.
- Debug controls are intentionally available for development and should be protected or removed before any public deployment.

## Thanks

 - Thanks NextSpaceFlight for the milestones
 - Thanks NSF for the awesome streams
 - Thanks Jay (from NSF) for some questions
 - Thanks SpaceX for putting the clock visible on the internet
