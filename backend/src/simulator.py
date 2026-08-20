import os
import json
import time
import random
import requests
from datetime import datetime

# Import the auth function we wrote yesterday
from auth import get_cognito_token

# Configure these via environment variables or replace locally for testing
API_URL = os.environ.get("API_URL", "https://replace-me-with-api-gateway-url/prod/events")
CLIENT_ID = os.environ.get("COGNITO_CLIENT_ID", "your-client-id-here")
CLIENT_SECRET = os.environ.get("COGNITO_CLIENT_SECRET", None) # None for Public Clients
USERNAME = os.environ.get("COGNITO_USERNAME", "test_user@campuspulse.com")
PASSWORD = os.environ.get("COGNITO_PASSWORD", "@User123")
REGION = os.environ.get("AWS_DEFAULT_REGION", "eu-north-1")

BUILDINGS = ["BLDG-A", "BLDG-B", "BLDG-C", "LIBRARY", "GYM"]
EVENT_TYPES = ["occupancy", "temperature", "energy"]

def generate_payload():
    building_id = random.choice(BUILDINGS)
    event_type = random.choice(EVENT_TYPES)
    
    payload = {
        "building_id": building_id,
        "timestamp": datetime.utcnow().isoformat(),
        "event_type": event_type,
    }
    
    if event_type == "occupancy":
        payload["occupancy_count"] = random.randint(0, 500)
    elif event_type == "temperature":
        temp = round(random.uniform(18.0, 30.0), 1)
        payload["temperature_c"] = temp
        if temp > 25.0:
            payload["alert"] = True
    elif event_type == "energy":
        payload["energy_kwh"] = round(random.uniform(10.0, 100.0), 2)
        
    return payload

def main():
    print(f"[*] Starting CampusPulse IoT Simulator...")
    print(f"[*] Authenticating with Cognito ({REGION})...")
    
    try:
        token = get_cognito_token(
            username=USERNAME,
            password=PASSWORD,
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
            region=REGION
        )
        print(f"[+] Authentication Successful! Token acquired.\n")
    except Exception as e:
        print(f"[!] Authentication Failed: {e}")
        print("[!] Make sure your COGNITO_CLIENT_ID and credentials are correct.")
        return
        
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }

    print(f"[*] Sending data to {API_URL} every 5 seconds. Press Ctrl+C to stop.")
    
    while True:
        payload = generate_payload()
        print(f"  -> Sending {payload['event_type']} event for {payload['building_id']}... ", end="")
        
        try:
            response = requests.post(API_URL, headers=headers, json=payload, timeout=5)
            if response.status_code in [200, 201]:
                print(f"SUCCESS ({response.status_code})")
            else:
                print(f"FAILED ({response.status_code}) - {response.text}")
        except requests.exceptions.RequestException as e:
            print(f"ERROR: {e}")
            
        time.sleep(5)

if __name__ == "__main__":
    main()
