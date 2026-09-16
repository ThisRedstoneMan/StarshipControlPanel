"""Fetch the StageSep launch weather-GO assessment.

Rewritten against the public stagesep-api
(https://github.com/smellyfingernail/stagesep-api). The old version
scraped percentages out of the human-readable `summary` sentence with
regexes; the API now publishes them as real numeric fields
(`go_window_open` / `go_window_any`, 0-1 fractions), so we read those
directly instead.
"""

import json
from urllib.request import Request, urlopen
from urllib.error import URLError

# "Current assessment" endpoint — stable, agent-friendly, always reflects
# the next/most-recent flight. Republished roughly every 10 minutes
# (`refreshMinutes` in the payload itself) — don't poll faster than that.
STAGESEP_LAUNCH_LATEST_URL = "https://stagesep.com/public/launch/latest.json"


def fetch_weather_probability(url=STAGESEP_LAUNCH_LATEST_URL, timeout=10):
	"""Return the latest overall and window-open GO percentages, plus
	some descriptive context from the same payload.

	Raises OSError/ValueError/json.JSONDecodeError on failure, same as the
	original implementation, so the try/except in fetch_clock_async keeps
	working unchanged.

	Two states from the API (see README "Current assessment" section):

	- live: a launch window is set. go_window_open / go_window_any are
	  0-1 fractions.
	- awaiting-window: between flights. Both fields are null — this is
	  documented, expected behavior, not an error, so we return None
	  percentages rather than raising.

	If status is (or looks like) "live" but the percentages are still
	missing, that's an unexpected payload shape, so we raise ValueError
	same as the old regex-based version did when it couldn't find both
	numbers.
	"""
	request = Request(
		url,
		headers={"User-Agent": "StarshipControlPane/1.0"},
	)
	try:
		with urlopen(request, timeout=timeout) as response:
			assessment = json.loads(response.read().decode("utf-8"))
	except URLError as error:
		raise OSError(f"Failed to reach stagesep-api: {error}") from error

	if not isinstance(assessment, dict):
		raise ValueError("Unexpected stagesep-api payload (not a JSON object).")

	status = assessment.get("status", "live")
	go_window_open = assessment.get("go_window_open")
	go_window_any = assessment.get("go_window_any")

	if status == "awaiting-window":
		overall_go = None
		window_open_go = None
	else:
		if go_window_open is None or go_window_any is None:
			raise ValueError("stagesep-api response did not contain both weather percentages")
		# Convert the API's 0-1 fractions to 0-100 percentages, matching
		# the shape the rest of the program (and the old scraper) expects.
		overall_go = round(go_window_any * 100, 1)
		window_open_go = round(go_window_open * 100, 1)

	return {
		"overall_go_percent": overall_go,
		"window_open_percent": window_open_go,
		# Extra context the old regex scraper couldn't easily get at,
		# since it only had the prose summary to work with. Harmless
		# additions: main.py's dict.update() just merges them in
		# alongside the manually-toggled "go" flag, which this function
		# never touches.
		"status": status,
		"summary": assessment.get("summary"),
		"mission": assessment.get("mission"),
		"schedule_confidence": assessment.get("scheduleConfidence"),
		"model_confidence": assessment.get("confidence"),
		"window_open_utc": assessment.get("windowOpenUTC"),
		"window_close_utc": assessment.get("windowCloseUTC"),
		"window_estimate": assessment.get("windowEstimate"),
		"dashboard_url": assessment.get("dashboardUrl"),
		"generated_at_utc": assessment.get("generatedAtUTC"),
		"refresh_minutes": assessment.get("refreshMinutes"),
		"launched": assessment.get("launched"),
		"scrubbed": assessment.get("scrubbed"),
		"last_flight": assessment.get("lastFlight"),
	}
