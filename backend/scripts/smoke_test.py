"""End-to-end API smoke test against the deployed stage.

Checks authentication, role enforcement, validation, ingestion and every read
endpoint, and prints latency figures for the report's testing section.

    COGNITO_CLIENT_ID=... COGNITO_USERNAME=admin@... COGNITO_PASSWORD=... python smoke_test.py
    (optional) STAFF_USERNAME / STAFF_PASSWORD to also verify the read-only role
"""
import os
import statistics
import sys
import time

import requests

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))
from auth import get_cognito_token  # noqa: E402

API_URL = os.environ.get("API_URL", "https://w1k2uj34k5.execute-api.eu-north-1.amazonaws.com/prod").rstrip("/")
CLIENT_ID = os.environ["COGNITO_CLIENT_ID"]

failures = 0


def check(name, response, expected):
    global failures
    ok = response.status_code == expected
    failures += not ok
    print(f"[{'PASS' if ok else 'FAIL'}] {name}: {response.status_code} (expected {expected}) "
          f"{response.elapsed.total_seconds() * 1000:.0f} ms")


def token_for(user_var, password_var):
    return get_cognito_token(os.environ[user_var], os.environ[password_var], CLIENT_ID)


def main():
    admin = {"Authorization": token_for("COGNITO_USERNAME", "COGNITO_PASSWORD")}
    good = {"building_id": "BLDG-A", "event_type": "temperature", "temperature_c": 22.4}

    check("POST /events without token", requests.post(f"{API_URL}/events", json=good), 401)
    check("GET /stats without token", requests.get(f"{API_URL}/stats"), 401)
    check("POST /events invalid payload", requests.post(f"{API_URL}/events", headers=admin,
                                                       json={"building_id": "BLDG-A", "event_type": "humidity"}), 400)
    check("POST /events valid (Admin)", requests.post(f"{API_URL}/events", headers=admin, json=good), 201)
    check("GET /stats campus overview", requests.get(f"{API_URL}/stats", headers=admin), 200)
    check("GET /stats?building_id=BLDG-A", requests.get(f"{API_URL}/stats", headers=admin,
                                                        params={"building_id": "BLDG-A"}), 200)
    check("GET /events?limit=10", requests.get(f"{API_URL}/events", headers=admin, params={"limit": 10}), 200)
    check("GET /alerts", requests.get(f"{API_URL}/alerts", headers=admin), 200)

    if os.environ.get("STAFF_USERNAME"):
        staff = {"Authorization": token_for("STAFF_USERNAME", "STAFF_PASSWORD")}
        check("GET /stats as Staff", requests.get(f"{API_URL}/stats", headers=staff), 200)
        check("POST /events as Staff (read-only)", requests.post(f"{API_URL}/events", headers=staff, json=good), 403)

    # Small latency sample for the performance section of the report.
    timings = []
    for _ in range(20):
        start = time.perf_counter()
        requests.post(f"{API_URL}/events", headers=admin, json=good, timeout=10)
        timings.append((time.perf_counter() - start) * 1000)
    timings.sort()
    print(f"\nPOST /events latency over 20 calls: median {statistics.median(timings):.0f} ms, "
          f"p95 {timings[int(len(timings) * 0.95) - 1]:.0f} ms, max {timings[-1]:.0f} ms")

    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
