"""CampusPulse IoT simulator.

Generates occupancy, temperature and energy readings for every campus building
and sends them to POST /events using a Cognito account in the Sensor (or Admin)
group. Configuration comes from environment variables; no credentials are
stored in the code.

    COGNITO_CLIENT_ID, COGNITO_USERNAME, COGNITO_PASSWORD   (required)
    API_URL            base URL of the API stage
    INTERVAL_SECONDS   pause between rounds (default 1)
    ROUNDS             stop after N rounds (default: run forever)

Example: python simulator.py            (one reading per building per second)
         ROUNDS=20 INTERVAL_SECONDS=0 python simulator.py   (burst / load test)
"""
import os
import random
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import requests

from auth import get_cognito_token

API_URL = os.environ.get("API_URL", "https://w1k2uj34k5.execute-api.eu-north-1.amazonaws.com/prod").rstrip("/")
CLIENT_ID = os.environ.get("COGNITO_CLIENT_ID")
CLIENT_SECRET = os.environ.get("COGNITO_CLIENT_SECRET")  # only for confidential app clients
USERNAME = os.environ.get("COGNITO_USERNAME")
PASSWORD = os.environ.get("COGNITO_PASSWORD")
REGION = os.environ.get("AWS_DEFAULT_REGION", "eu-north-1")
INTERVAL_SECONDS = float(os.environ.get("INTERVAL_SECONDS", "1"))
ROUNDS = int(os.environ.get("ROUNDS", "0"))

# Must match BUILDINGS in common.py and the dashboard.
BUILDINGS = ["BLDG-A", "BLDG-B", "LIBRARY", "GYM", "Engineering"]
EVENT_TYPES = ["occupancy", "temperature", "energy"]


def generate_payload(building_id, event_type):
    """Random reading; roughly 1 in 8 readings crosses the anomaly threshold."""
    payload = {
        "building_id": building_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_type": event_type,
    }
    if event_type == "occupancy":
        payload["occupancy_count"] = random.randint(20, 170)
    elif event_type == "temperature":
        payload["temperature_c"] = round(random.uniform(19.0, 29.5), 1)
    else:
        payload["energy_kwh"] = round(random.uniform(40.0, 130.0), 1)
    return payload


def login():
    return get_cognito_token(
        username=USERNAME,
        password=PASSWORD,
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        region=REGION,
    )


def send(session, token, payload):
    return session.post(
        f"{API_URL}/events",
        headers={"Authorization": token, "Content-Type": "application/json"},
        json=payload,
        timeout=10,
    )


def main():
    missing = [n for n, v in [("COGNITO_CLIENT_ID", CLIENT_ID), ("COGNITO_USERNAME", USERNAME),
                              ("COGNITO_PASSWORD", PASSWORD)] if not v]
    if missing:
        sys.exit(f"[!] Set the environment variables: {', '.join(missing)}")

    print(f"[*] Authenticating {USERNAME} with Cognito ({REGION})...")
    token = login()
    print(f"[+] Token acquired. Sending to {API_URL}/events. Ctrl+C to stop.\n")

    session = requests.Session()
    sent = failed = 0
    round_no = 0
    with ThreadPoolExecutor(max_workers=len(BUILDINGS)) as pool:
        while not ROUNDS or round_no < ROUNDS:
            round_no += 1
            # One reading per building per round, of a rotating event type.
            payloads = [generate_payload(b, EVENT_TYPES[round_no % len(EVENT_TYPES)]) for b in BUILDINGS]
            started = time.perf_counter()
            results = list(pool.map(lambda p: send(session, token, p), payloads))

            if any(r.status_code == 401 for r in results):
                print("[*] Token expired, re-authenticating...")
                token = login()
                continue

            for payload, r in zip(payloads, results):
                if r.status_code == 201:
                    sent += 1
                    severity = r.json().get("severity")
                    flag = "  <-- ANOMALY" if severity == "critical" else ""
                    print(f"  {payload['building_id']:<12} {payload['event_type']:<12} 201{flag}")
                else:
                    failed += 1
                    print(f"  {payload['building_id']:<12} {payload['event_type']:<12} {r.status_code} {r.text}")
            print(f"[round {round_no}] {len(payloads)} events in {(time.perf_counter() - started) * 1000:.0f} ms "
                  f"(total ok={sent} failed={failed})")
            time.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
