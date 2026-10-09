"""Run the CampusPulse IoT sensor simulator from a laptop, without environment variables.

The first run (or --setup) asks for the sensor account's login and saves it to
scripts/.sensor_creds.json, which is git-ignored. Later runs start straight away.

    uv run python scripts/run_sensors.py                      # one reading per building per second, until Ctrl+C
    uv run python scripts/run_sensors.py --interval 3         # slower: one round every 3 seconds
    uv run python scripts/run_sensors.py --rounds 40 --interval 0   # burst test: 200 events as fast as possible
    uv run python scripts/run_sensors.py --setup              # enter or change the login

Use an account in the Cognito "Sensor" group (or "Admin"); Staff accounts are
read-only and every event would be rejected with HTTP 403.
"""
import argparse
import getpass
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "src")
CREDS_FILE = os.path.join(HERE, ".sensor_creds.json")

COGNITO_CLIENT_ID = "3a3f1jain8aistg3rq35q3jv8i"   # public app client ID
API_URL = "https://w1k2uj34k5.execute-api.eu-north-1.amazonaws.com/prod"


def load():
    if not os.path.exists(CREDS_FILE):
        return {}
    with open(CREDS_FILE, encoding="utf-8") as f:
        return json.load(f)


def setup():
    saved = load()
    default = saved.get("email", "sensor@test.fr")
    email = input(f"Sensor account email [{default}]: ").strip() or default
    password = getpass.getpass("Password (hidden): ")
    creds = {"email": email, "password": password}
    with open(CREDS_FILE, "w", encoding="utf-8") as f:
        json.dump(creds, f, indent=2)
    print(f"Saved to {CREDS_FILE} (git-ignored).\n")
    return creds


def main():
    parser = argparse.ArgumentParser(description="CampusPulse IoT sensor simulator (laptop runner)")
    parser.add_argument("--setup", action="store_true", help="enter or change the saved login")
    parser.add_argument("--interval", type=float, default=1.0, help="seconds between rounds (default 1)")
    parser.add_argument("--rounds", type=int, default=0, help="stop after N rounds (default: run until Ctrl+C)")
    args = parser.parse_args()

    creds = load()
    if args.setup or not creds.get("password"):
        creds = setup()

    # simulator.py reads its settings from the environment when it is imported;
    # they are set here for this process only.
    os.environ.update({
        "COGNITO_CLIENT_ID": COGNITO_CLIENT_ID,
        "API_URL": API_URL,
        "COGNITO_USERNAME": creds["email"],
        "COGNITO_PASSWORD": creds["password"],
        "INTERVAL_SECONDS": str(args.interval),
        "ROUNDS": str(args.rounds),
    })
    sys.path.insert(0, os.path.abspath(SRC))
    import simulator  # noqa: E402

    print("Five buildings, one reading each per round; the event type rotates every round.")
    try:
        simulator.main()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
