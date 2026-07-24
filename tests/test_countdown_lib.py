import unittest
from unittest.mock import patch

from libraries.countdownLib import getLaunchDetails


class CountdownLibTests(unittest.TestCase):
    def test_get_launch_details_uses_future_missions_payload(self):
        payload = {
            "F343A80AAFA11416DBEA660C9ADB5728982363A1DB46756A4C4C86849048088B": {
                "CorrelationId": "F343A80AAFA11416DBEA660C9ADB5728982363A1DB46756A4C4C86849048088B",
                "PrimaryLaunchDate": None,
                "PrimaryLaunchWindow": None,
                "TZeroLaunchDate": {"Seconds": 1784933100, "Nanos": 0},
            }
        }

        class FakeResponse:
            def raise_for_status(self):
                return None

            def json(self):
                return payload

        with patch("requests.get", return_value=FakeResponse()):
            details = getLaunchDetails("https://content.spacex.com/cms-assets/future_missions.json", "F343A80AAFA11416DBEA660C9ADB5728982363A1DB46756A4C4C86849048088B")

        self.assertEqual(details["launch_timestamp"], 1784933100)
        self.assertIsNone(details["window_start"])
        self.assertIsNone(details["window_end"])


if __name__ == "__main__":
    unittest.main()
