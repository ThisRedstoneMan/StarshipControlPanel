def format_seconds_to_clock(signed_seconds):
        prefix = "T- " if signed_seconds < 0 else "T+ "
        abs_secs = abs(signed_seconds)
        hours = abs_secs // 3600
        minutes = (abs_secs % 3600) // 60
        seconds = abs_secs % 60
        return f"{prefix}{hours:02d} : {minutes:02d} : {seconds:02d}"

def getSignedSecondsFromT0(url, flightID):
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
        
        launch_time = datetime.fromtimestamp(launch_time_timestamp, tz=timezone.utc)
        current_time = datetime.now(timezone.utc)
        
        # Calculate signed seconds
        signed_seconds = int((current_time - launch_time).total_seconds())
        
        return signed_seconds
    
    except requests.RequestException as e:
        print(f"Error fetching data from {url}: {e}")
        return None
    except ValueError as ve:
        print(ve)
        return None     