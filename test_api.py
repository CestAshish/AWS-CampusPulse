import urllib.request
import json
import random
import datetime
import time

api_url = 'https://w1k2uj34k5.execute-api.eu-north-1.amazonaws.com/prod/events'
buildings = ['BLDG-A', 'BLDG-B', 'LIBRARY', 'GYM', 'Engineering']
event_types = ['temperature', 'occupancy', 'energy']

print('Sending 15 events...')
for i in range(15):
    bldg = random.choice(buildings)
    evt = random.choice(event_types)
    val = round(random.uniform(18, 28), 1) if evt == 'temperature' else random.randint(10, 200) if evt == 'occupancy' else round(random.uniform(50, 500), 2)
    unit = 'C' if evt == 'temperature' else 'people' if evt == 'occupancy' else 'kWh'
    payload = {
        'building_id': bldg,
        'event_type': evt,
        'timestamp': datetime.datetime.utcnow().isoformat(),
        'value': val,
        'unit': unit
    }
    
    req = urllib.request.Request(
        api_url, 
        method='POST', 
        headers={'Content-Type': 'application/json'}, 
        data=json.dumps(payload).encode('utf-8')
    )
    resp = urllib.request.urlopen(req)
    print(f'Sent {i+1}/15: {bldg} {evt} -> Status {resp.getcode()}')
    time.sleep(0.5)
