import json
import requests

url = 'https://content.spacex.com/api/spacex-website/launches-page-tiles/upcoming'
flight = 'F343A80AAFA11416DBEA660C9ADB5728982363A1DB46756A4C4C86849048088B'

response = requests.get(url, timeout=20)
response.raise_for_status()
data = response.json()
mission = next((m for m in data if m.get('correlationId') == flight), None)
print(json.dumps(mission, indent=2)[:12000])
