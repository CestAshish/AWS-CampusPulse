"""Shared helpers for the CampusPulse Lambda functions.

Holds the event schema, the anomaly thresholds and the role checks so that the
ingest and query functions (and the tests) all agree on the same rules.
"""
import json
import re
from decimal import Decimal

BUILDINGS = ["BLDG-A", "BLDG-B", "LIBRARY", "GYM", "Engineering"]

# One entry per supported sensor type: the payload field that carries the
# reading, its unit, the physically plausible range accepted by validation and
# the threshold above which the event is flagged as an anomaly.
EVENT_TYPES = {
    "temperature": {"field": "temperature_c", "unit": "C", "min": -30.0, "max": 60.0, "alert_above": 28.0},
    "occupancy": {"field": "occupancy_count", "unit": "people", "min": 0, "max": 1000, "alert_above": 150},
    "energy": {"field": "energy_kwh", "unit": "kWh", "min": 0.0, "max": 1000.0, "alert_above": 120.0},
}

# Cognito groups. Admin can do everything, Sensor devices can only ingest,
# Staff is the read-only operations role.
ROLE_ADMIN = "Admin"
ROLE_STAFF = "Staff"
ROLE_SENSOR = "Sensor"
INGEST_ROLES = {ROLE_ADMIN, ROLE_SENSOR}
READ_ROLES = {ROLE_ADMIN, ROLE_STAFF}

ALERT_PARTITION = "ALERT"
TTL_DAYS = 30

BUILDING_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,32}$")

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type,Authorization",
    "Access-Control-Allow-Methods": "OPTIONS,POST,GET",
}


class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return int(obj) if obj % 1 == 0 else float(obj)
        return super().default(obj)


def response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": CORS_HEADERS,
        "body": json.dumps(body, cls=DecimalEncoder),
    }


def caller_groups(event):
    """Return the Cognito groups of the caller from the authorizer claims.

    API Gateway (REST, Cognito authorizer) passes `cognito:groups` as a string,
    e.g. "Admin" or "[Admin, Staff]", so both forms are handled.
    """
    claims = ((event.get("requestContext") or {}).get("authorizer") or {}).get("claims") or {}
    raw = claims.get("cognito:groups", "")
    if isinstance(raw, list):
        return set(raw)
    return {g for g in re.split(r"[\s,\[\]]+", raw) if g}


def is_allowed(event, roles):
    return bool(caller_groups(event) & roles)
