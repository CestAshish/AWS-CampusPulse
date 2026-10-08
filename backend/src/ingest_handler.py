import json
import os
import time
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import boto3

from common import (
    ALERT_PARTITION,
    BUILDING_ID_PATTERN,
    EVENT_TYPES,
    INGEST_ROLES,
    TTL_DAYS,
    is_allowed,
    response,
)

dynamodb = boto3.resource('dynamodb', region_name='eu-north-1')
table = dynamodb.Table(os.environ['TABLE_NAME'])


class ValidationError(Exception):
    pass


def validate(body):
    """Validate an incoming sensor event and return the normalised fields."""
    if not isinstance(body, dict):
        raise ValidationError("Body must be a JSON object")

    building_id = body.get('building_id')
    if not isinstance(building_id, str) or not BUILDING_ID_PATTERN.match(building_id):
        raise ValidationError("building_id is required (1-32 letters, digits, '-' or '_')")

    event_type = body.get('event_type')
    if event_type not in EVENT_TYPES:
        raise ValidationError(f"event_type must be one of {sorted(EVENT_TYPES)}")

    spec = EVENT_TYPES[event_type]
    raw_value = body.get(spec['field'])
    try:
        value = float(raw_value)
    except (TypeError, ValueError):
        raise ValidationError(f"{spec['field']} is required and must be a number for {event_type} events")
    if not spec['min'] <= value <= spec['max']:
        raise ValidationError(f"{spec['field']} must be between {spec['min']} and {spec['max']}")

    timestamp = body.get('timestamp') or datetime.now(timezone.utc).isoformat()
    try:
        datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
    except (AttributeError, ValueError):
        raise ValidationError("timestamp must be an ISO 8601 string")

    return building_id, event_type, spec, value, timestamp


def emit_metrics(event_type, value, alert):
    """Publish custom metrics using CloudWatch Embedded Metric Format.

    The metric is written as a structured log line, so the function needs no
    network route to the CloudWatch API and can stay in a private subnet.
    """
    metric_name = {'occupancy': 'OccupancyCount', 'temperature': 'Temperature', 'energy': 'EnergyUsage'}[event_type]
    print(json.dumps({
        '_aws': {
            'Timestamp': int(time.time() * 1000),
            'CloudWatchMetrics': [{
                'Namespace': 'CampusPulse',
                'Dimensions': [['Service']],
                'Metrics': [
                    {'Name': metric_name, 'Unit': 'Count' if event_type == 'occupancy' else 'None'},
                    {'Name': 'AnomalyCount', 'Unit': 'Count'},
                ],
            }],
        },
        'Service': 'CampusPulse',
        metric_name: value,
        'AnomalyCount': 1 if alert else 0,
    }))


def lambda_handler(event, context):
    if not is_allowed(event, INGEST_ROLES):
        return response(403, {'error': 'Only Admin or Sensor accounts can submit events'})

    try:
        body = json.loads(event.get('body') or '{}')
        building_id, event_type, spec, value, timestamp = validate(body)
    except json.JSONDecodeError:
        return response(400, {'error': 'Body must be valid JSON'})
    except ValidationError as e:
        return response(400, {'error': str(e)})

    # Anomaly detection is done server-side so a sensor cannot hide an alert.
    alert = value > spec['alert_above']
    event_id = f"evt-{uuid.uuid4().hex[:12]}"
    item = {
        'building_id': building_id,
        'timestamp': timestamp,
        'event_id': event_id,
        'event_type': event_type,
        spec['field']: int(value) if event_type == 'occupancy' else Decimal(str(value)),
        'unit': spec['unit'],
        'alert': alert,
        'severity': 'critical' if alert else 'normal',
        'expires_at': int(time.time()) + TTL_DAYS * 86400,
    }
    if alert:
        # Sparse attribute: only anomalies appear in the AlertIndex GSI.
        item['alert_status'] = ALERT_PARTITION

    try:
        table.put_item(Item=item)
    except Exception as e:
        print(json.dumps({'level': 'ERROR', 'message': 'put_item failed', 'error': str(e)}))
        return response(500, {'error': 'Could not store event'})

    emit_metrics(event_type, value, alert)
    return response(201, {
        'message': 'Event ingested successfully',
        'event_id': event_id,
        'severity': item['severity'],
    })
