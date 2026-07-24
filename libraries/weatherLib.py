"""Fetch and parse the StageSep launch weather probability summary."""

import json
import re
from urllib.request import Request, urlopen


STAGESEP_LAUNCH_PROBABILITY_URL = "https://stagesep.com/launch-probability/"
STAGESEP_LAUNCH_LATEST_URL = "https://stagesep.com/public/launch/latest.json"
_PERCENTAGE = r"(\d+(?:\.\d+)?)%"


def _percentage_after(label, page_text):
	match = re.search(
		rf"{label}\s*{_PERCENTAGE}",
		page_text,
		flags=re.IGNORECASE,
	)
	return float(match.group(1)) if match else None


def fetch_weather_probability(url=STAGESEP_LAUNCH_LATEST_URL, timeout=10):
	"""Return the latest overall and window-open GO percentages.

	StageSep publishes the current assessment as JSON. The summary is plain
	text, so the percentages are extracted from that field rather than from
	the client-rendered dashboard HTML.
	"""
	request = Request(
		url,
		headers={"User-Agent": "StarshipControlPane/1.0"},
	)
	with urlopen(request, timeout=timeout) as response:
		assessment = json.loads(response.read().decode("utf-8"))

	summary = assessment.get("summary", "")
	window_open_go = _percentage_after(r"is\s+", summary)
	overall_match = re.search(
		rf"with\s+an?\s+{_PERCENTAGE}\s+chance\s+of\s+at\s+least\s+one\s+GO\s+hour",
		summary,
		flags=re.IGNORECASE,
	)
	overall_go = float(overall_match.group(1)) if overall_match else None
	if overall_go is None or window_open_go is None:
		raise ValueError("StageSep page did not contain both weather percentages")

	return {
		"overall_go_percent": overall_go,
		"window_open_percent": window_open_go,
	}
