# Starship Control Panel

A small Python command-line utility that displays a live Starship mission clock relative to a configured launch time.

The app retrieves SpaceX future-mission data, finds the selected flight by ID, and prints a clock in `T- HH : MM : SS` before launch or `T+ HH : MM : SS` after launch.

## Requirements

- Python 3
- The `requests` package

Install the dependency:

```bash
pip install requests
```

## Run

```bash
python main.py
```

The clock refreshes every 0.5 seconds. Stop it with `Ctrl+C`.

## Configuration

In `main.py`, update these values to select a mission and refresh rate:

```python
spacexCountdownUrl = "https://content.spacex.com/cms-assets/future_missions.json"
flightID = "..."
updateInterval = 0.5
```

## Project layout

- `main.py` - entry point and repeating countdown display.
- `libraries/countdownLib.py` - fetches mission data, calculates time from launch, and formats the clock.
- `libraries/generalLib.py` - cross-platform system-beep helper.
- `data/milestones.json` - planned countdown and flight milestone data.
