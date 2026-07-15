from libraries.countdownLib import getSignedSecondsFromT0, format_seconds_to_clock
import time


spacexCountdownUrl = "https://content.spacex.com/cms-assets/future_missions.json"
flightID = "F343A80AAFA11416DBEA660C9ADB5728982363A1DB46756A4C4C86849048088B"
signed_seconds = getSignedSecondsFromT0(spacexCountdownUrl, flightID)
updateInterval = 0.5 #in seconds
running = True

def getCountdownClock():
    signedSeconds = getSignedSecondsFromT0(spacexCountdownUrl, flightID)
    if signedSeconds is not None:
        countdown_clock = format_seconds_to_clock(signedSeconds)
        return countdown_clock
    else:
        return "Error retrieving countdown clock."
while running:
    countdown_clock = getCountdownClock()
    print(countdown_clock)
    time.sleep(updateInterval)