# Starship Control Panel

A lightweight, real-time Starship launch dashboard for a browser on your computer or local network. It polls the SpaceX launch-data feed, renders a mission timeline, tracks countdown state, and broadcasts live status updates to every connected browser over WebSockets.

## What the app does

- Shows a live T-/T+ countdown clock, phase, and latest milestone.
- Renders a mission timeline with an animated marker that moves smoothly between updates.
- Displays a visible launch-window bar with a red dot and a flashing red state when the current launch time falls outside the active window.
- Detects countdown holds, resumed countdowns, delays, and other timestamp changes from the upstream SpaceX data.
- Tracks a post-load hold-fuel budget after the configured load-complete milestone.
- Exposes shared status indicators for weather, pad clear, road closure close, road closure far, tank farm chilldown, go for prop load, and flight director. The flight director status automatically goes to GO when the countdown is under 30 seconds.
- Includes local debug controls for time scrubbing, server-side countdown jumps, simulated holds/delays, and status toggles.

## Requirements

- Python 3.10 or newer
- Internet access so the app can fetch the SpaceX launch-data feed
- A modern browser
- The following Python packages:

```bash
python -m pip install fastapi "uvicorn[standard]" requests
```

## Run locally

From the repository root, start the app with either of these commands:

```bash
python launcher.py (recommanded)
```

or:

```bash
python server.py
```

Then open:

```text
http://127.0.0.1:8000
```

The server listens on `0.0.0.0`, so devices on the same local network can also open it using your computer's LAN IP address, for example:

```text
http://YOUR-COMPUTER-LAN-IP:8000
```

If the browser cannot connect, allow Python through your firewall for private networks.

Stop the server with q and reboot it with enter (ONLY WORKS IF LAUNCHED WITH launcher.py).

## Change the debug password

You can change the password in the server.py
Change the "coolPassword" in this example with the actual password you want to use. 

```
DEBUG_PASSWORD = os.environ.get("STARSHIP_DEBUG_PASSWORD", "coolPassword")
if DEBUG_PASSWORD == "coolPassword":
    print(
        "[debug-auth] WARNING: using the default debug password. "
        "Set STARSHIP_DEBUG_PASSWORD to something private before sharing this on your LAN."
    )
```

## Project structure

```text
.
+-- data/
|   +-- milestones.json       # Timeline milestones relative to T-0
+-- libraries/
|   +-- countdownLib.py       # SpaceX data parsing, timestamp helpers, countdown formatting
|   +-- generalLib.py         # Small cross-platform utility helper
+-- web/
|   +-- index.html            # Dashboard UI, status boxes, window bar, debug tools
|   +-- timeline.js           # SVG-based elastic timeline renderer
+-- launcher.py               # Helper that restarts server.py in a loop
+-- main.py                   # Countdown logic, hold/delay detection, shared state
+-- server.py                 # FastAPI app, static file serving, WebSocket broadcast
```

## How it works

```text
SpaceX mission data
        |
        v
main.py: fetch launch details, compute countdown, detect timestamp changes
        |
        v
shared current_state dictionary
        |
        v
server.py: FastAPI + WebSocket broadcast every 0.5 seconds
        |
        v
web/index.html + web/timeline.js: browser dashboard and timeline
```

The app polls the configured SpaceX launch tiles endpoint, computes the signed countdown from the target launch timestamp, and passes the live state to the browser over `/ws/state`.

## Configuration

The main mission settings are defined near the top of [main.py](main.py):

```python
spacexCountdownUrl = "https://content.spacex.com/api/spacex-website/launches-page-tiles/upcoming"
flightID = "F343A80AAFA11416DBEA660C9ADB5728982363A1DB46756A4C4C86849048088B"
fetchInterval = 0.5
updateInterval = 0.1
```

You can change the mission ID or polling rate there if needed.

The hold-fuel budget and prop-load milestone offsets are also defined in [main.py](main.py):

```python
LOAD_COMPLETE_OFFSET = -130
HOLD_FUEL_BUDGET_SECONDS = 10 * 60
```

## Milestones

The timeline milestones come from [data/milestones.json](data/milestones.json). Each item should look like this:

```json
{
  "name": "Liftoff",
  "time": 0
}
```

Use negative values for events before launch and positive values for events after launch. Keep the list in chronological order for the clearest timeline.

## Hold and delay detection

Each successful poll compares the new launch timestamp with the previous one.

| Change detected | Result |
| --- | --- |
| No meaningful change | No event |
| Small change | Hold / resumed countdown |
| Larger change | Delay / major schedule move |

Positive changes push T-0 later; negative changes move it earlier. Consecutive small slips are grouped into one active hold event so the banner and history remain readable.

## Hold-fuel budget

The dashboard uses the configured milestone in [data/milestones.json](data/milestones.json) to define the prop-load-complete point at T-2:10. From that point onward, a 10-minute hold-fuel allowance is visualized.

- The bar is inactive before the load-complete milestone.
- After that, the budget turns green, amber, or red depending on how much remains.
- A major delay or a return to before the load-complete milestone resets the budget for a new attempt.

This is a visualization aid for the dashboard, not official launch-provider telemetry.

## Debug tools

Enable Debug tools in the top-left of the dashboard to reveal the local testing controls.

- Manual time override previews a timeline point in the browser only.
- Jump countdown here commits the selected time to the server and resets the hold-fuel budget.
- Advance countdown moves the server-side countdown forward without resetting the hold-fuel budget.
- +30s delay, +5min delay, and +1hr delay simulate T-0 shifts through the real detection pipeline.
- Continuous hold advances T-0 by one second per real second.
- Toggle Weather, Pad Clear, Road Closure Close, Road Closure Far, Tank Farm Chilldown, Go for Prop Load, and Flight Director change the shared status indicators for every connected browser.
- Clear simulation restores the live countdown state.

The debug routes are intentionally local-only and should not be exposed to the public internet.

## HTTP and WebSocket endpoints

| Endpoint | Purpose |
| --- | --- |
| `GET /` | Dashboard HTML and static assets |
| `WS /ws/state` | Live dashboard state |
| `POST /debug/simulate?delta_seconds=...` | Simulate a T-0 hold or delay |
| `POST /debug/set-time?signed_seconds=...` | Set a server-side debug countdown time |
| `POST /debug/advance?seconds=...` | Advance the server-side countdown |
| `POST /debug/toggle-weather` | Toggle the shared weather status |
| `POST /debug/toggle-pad-clear` | Toggle the shared pad-clear status |
| `POST /debug/toggle-road-closure-close` | Toggle the road-closure-close status |
| `POST /debug/toggle-road-closure-far` | Toggle the road-closure-far status |
| `POST /debug/toggle-tank-farm-chilldown` | Toggle the tank-farm-chilldown status |
| `POST /debug/toggle-prop-load` | Toggle the go-for-prop-load status |
| `POST /debug/toggle-flight-director-go` | Toggle the flight-director GO status |
| `POST /debug/gradual-hold?enabled=true` | Start or stop the continuous hold simulation |
| `POST /debug/clear` | Clear the debug override |

## Notes and limitations

- Countdown accuracy depends on the SpaceX data endpoint and the selected mission record.
- Launch timelines and windows can change without notice.
- Hold and fuel-budget behavior are visualization aids based on the available data, not official provider telemetry.
- The debug controls are intended for local development and testing.

## Thanks

- Thanks to NextSpaceFlight for the easy to copy milestones
- Thanks to NASASpacefslight for the live launch coverage and community discussion
- Thanks Jay (from NSF) for some questions
- Thanks to SpaceX for making countdown information visible on the internet