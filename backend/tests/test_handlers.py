import os
import sys
import json
import pytest
import boto3
from moto import mock_aws

import importlib

# Make both `src.x` and the Lambda-style flat imports (`from common import ...`) resolvable
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(BACKEND_DIR)
sys.path.append(os.path.join(BACKEND_DIR, 'src'))

# Set environment variables for Lambda and dummy AWS credentials for Moto
os.environ['TABLE_NAME'] = 'CampusPulseEvents'
os.environ['AWS_DEFAULT_REGION'] = 'eu-north-1'
os.environ['AWS_ACCESS_KEY_ID'] = 'testing'
os.environ['AWS_SECRET_ACCESS_KEY'] = 'testing'
os.environ['AWS_SECURITY_TOKEN'] = 'testing'
os.environ['AWS_SESSION_TOKEN'] = 'testing'

# Import handlers
from src import ingest_handler
from src import stats_handler


def as_role(group, **event):
    """Build an API Gateway proxy event for a caller in the given Cognito group."""
    event['requestContext'] = {'authorizer': {'claims': {'cognito:groups': group}}}
    return event


def post(group, payload):
    return ingest_handler.lambda_handler(as_role(group, body=json.dumps(payload)), None)


def get(group, resource, params=None):
    event = as_role(group, resource=resource, queryStringParameters=params)
    response = stats_handler.lambda_handler(event, None)
    return response['statusCode'], json.loads(response['body'])


@pytest.fixture
def dynamodb_mock():
    with mock_aws():
        # Reload modules inside the mock context so boto3 clients are mocked
        importlib.reload(ingest_handler)
        importlib.reload(stats_handler)

        dynamodb = boto3.resource('dynamodb', region_name='eu-north-1')
        # Same schema as backend/infra/dynamodb.tf
        table = dynamodb.create_table(
            TableName='CampusPulseEvents',
            KeySchema=[
                {'AttributeName': 'building_id', 'KeyType': 'HASH'},
                {'AttributeName': 'timestamp', 'KeyType': 'RANGE'}
            ],
            AttributeDefinitions=[
                {'AttributeName': 'building_id', 'AttributeType': 'S'},
                {'AttributeName': 'timestamp', 'AttributeType': 'S'},
                {'AttributeName': 'event_type', 'AttributeType': 'S'},
                {'AttributeName': 'alert_status', 'AttributeType': 'S'}
            ],
            BillingMode='PAY_PER_REQUEST',
            GlobalSecondaryIndexes=[
                {
                    'IndexName': 'EventTypeIndex',
                    'KeySchema': [
                        {'AttributeName': 'event_type', 'KeyType': 'HASH'},
                        {'AttributeName': 'timestamp', 'KeyType': 'RANGE'}
                    ],
                    'Projection': {'ProjectionType': 'ALL'}
                },
                {
                    'IndexName': 'AlertIndex',
                    'KeySchema': [
                        {'AttributeName': 'alert_status', 'KeyType': 'HASH'},
                        {'AttributeName': 'timestamp', 'KeyType': 'RANGE'}
                    ],
                    'Projection': {'ProjectionType': 'ALL'}
                }
            ]
        )
        yield table


# --- Ingestion -------------------------------------------------------------

def test_ingest_handler_success(dynamodb_mock):
    """A valid event from an Admin is stored with server-generated fields"""
    response = post('Admin', {'building_id': 'BLDG-A', 'event_type': 'occupancy', 'occupancy_count': 42})

    assert response['statusCode'] == 201
    body = json.loads(response['body'])
    assert body['severity'] == 'normal'

    items = dynamodb_mock.scan()['Items']
    assert len(items) == 1
    item = items[0]
    assert item['building_id'] == 'BLDG-A'
    assert item['occupancy_count'] == 42
    assert item['event_type'] == 'occupancy'
    assert item['event_id'].startswith('evt-')
    assert 'timestamp' in item      # auto-generated
    assert 'expires_at' in item     # TTL for cost control
    assert 'alert_status' not in item
    # Only the field belonging to the event type is stored
    assert 'temperature_c' not in item and 'energy_kwh' not in item


def test_sensor_role_can_ingest(dynamodb_mock):
    response = post('Sensor', {'building_id': 'GYM', 'event_type': 'energy', 'energy_kwh': 80.5})
    assert response['statusCode'] == 201


@pytest.mark.parametrize('group', ['Staff', '', '[Staff]'])
def test_read_only_roles_cannot_ingest(dynamodb_mock, group):
    response = post(group, {'building_id': 'GYM', 'event_type': 'energy', 'energy_kwh': 80.5})
    assert response['statusCode'] == 403
    assert dynamodb_mock.scan()['Count'] == 0


def test_multi_group_claim_is_parsed(dynamodb_mock):
    response = post('[Staff, Admin]', {'building_id': 'GYM', 'event_type': 'energy', 'energy_kwh': 80.5})
    assert response['statusCode'] == 201


@pytest.mark.parametrize('payload', [
    {'event_type': 'occupancy', 'occupancy_count': 5},                              # missing building
    {'building_id': 'BLDG A!', 'event_type': 'occupancy', 'occupancy_count': 5},    # bad building id
    {'building_id': 'GYM', 'event_type': 'humidity', 'value': 40},                  # unknown type
    {'building_id': 'GYM', 'event_type': 'temperature'},                            # missing reading
    {'building_id': 'GYM', 'event_type': 'temperature', 'temperature_c': 'hot'},    # not a number
    {'building_id': 'GYM', 'event_type': 'occupancy', 'occupancy_count': -3},       # out of range
    {'building_id': 'GYM', 'event_type': 'energy', 'energy_kwh': 5, 'timestamp': 'yesterday'},
])
def test_invalid_events_are_rejected(dynamodb_mock, payload):
    response = post('Admin', payload)
    assert response['statusCode'] == 400
    assert 'error' in json.loads(response['body'])
    assert dynamodb_mock.scan()['Count'] == 0


def test_malformed_json_is_rejected(dynamodb_mock):
    response = ingest_handler.lambda_handler(as_role('Admin', body='{not json'), None)
    assert response['statusCode'] == 400


def test_anomaly_is_detected_server_side(dynamodb_mock):
    """The server flags anomalies even if the sensor claims alert=False"""
    response = post('Sensor', {'building_id': 'LIBRARY', 'event_type': 'temperature',
                               'temperature_c': 31.2, 'alert': False})
    assert json.loads(response['body'])['severity'] == 'critical'

    item = dynamodb_mock.scan()['Items'][0]
    assert item['alert'] is True
    assert item['alert_status'] == 'ALERT'


def test_ingest_emits_embedded_metrics(dynamodb_mock, capsys):
    post('Admin', {'building_id': 'GYM', 'event_type': 'energy', 'energy_kwh': 130})
    log_line = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert log_line['_aws']['CloudWatchMetrics'][0]['Namespace'] == 'CampusPulse'
    assert log_line['EnergyUsage'] == 130
    assert log_line['AnomalyCount'] == 1
    assert log_line['Service'] == 'CampusPulse'


# --- Read API --------------------------------------------------------------

def seed(table):
    rows = [
        ('BLDG-A', '2026-08-19T10:00:00', 'temperature', 'temperature_c', '22.5'),
        ('BLDG-A', '2026-08-19T10:01:00', 'temperature', 'temperature_c', '29.5'),
        ('BLDG-A', '2026-08-19T10:02:00', 'occupancy', 'occupancy_count', 100),
        ('BLDG-A', '2026-08-19T10:03:00', 'energy', 'energy_kwh', '60'),
        ('GYM', '2026-08-19T10:00:30', 'occupancy', 'occupancy_count', 170),
        ('GYM', '2026-08-19T10:01:30', 'energy', 'energy_kwh', '125'),
    ]
    for building, ts, event_type, field, value in rows:
        item = {'building_id': building, 'timestamp': ts, 'event_type': event_type, field: value}
        spec = ingest_handler.EVENT_TYPES[event_type]
        if float(value) > spec['alert_above']:
            item['alert'] = True
            item['alert_status'] = 'ALERT'
        table.put_item(Item=item)


def test_stats_handler_success(dynamodb_mock):
    """GET /stats?building_id= returns aggregates plus chart points oldest-first"""
    seed(dynamodb_mock)
    status, body = get('Staff', '/stats', {'building_id': 'BLDG-A'})

    assert status == 200
    assert body['building_id'] == 'BLDG-A'
    assert body['total_events'] == 4
    assert [e['timestamp'] for e in body['data']] == sorted(e['timestamp'] for e in body['data'])
    temp = body['summary']['temperature']
    assert temp['latest'] == 29.5
    assert temp['avg'] == 26.0
    assert temp['min'] == 22.5 and temp['max'] == 29.5
    assert temp['anomalies'] == 1
    assert body['summary']['occupancy']['latest'] == 100
    assert body['alerts'] == 1


def test_campus_stats_ranks_energy_and_flags_overload(dynamodb_mock):
    seed(dynamodb_mock)
    status, body = get('Admin', '/stats')

    assert status == 200
    assert [b['building_id'] for b in body['energy_ranking']] == ['GYM', 'BLDG-A']
    assert body['overloaded'] == [{'building_id': 'GYM', 'occupancy': 170}]
    assert len(body['buildings']) == 5


def test_list_events_newest_first(dynamodb_mock):
    seed(dynamodb_mock)
    status, body = get('Staff', '/events', {'limit': '3'})
    assert status == 200
    assert body['count'] == 3
    assert body['events'][0]['timestamp'] == '2026-08-19T10:03:00'

    status, body = get('Staff', '/events', {'building_id': 'GYM', 'event_type': 'energy'})
    assert [float(e['energy_kwh']) for e in body['events']] == [125.0]


def test_list_alerts(dynamodb_mock):
    seed(dynamodb_mock)
    status, body = get('Staff', '/alerts')
    assert status == 200
    assert body['count'] == 3
    assert body['alerts'][0]['timestamp'] == '2026-08-19T10:01:30'


def test_sensor_role_cannot_read(dynamodb_mock):
    status, _ = get('Sensor', '/stats', {'building_id': 'BLDG-A'})
    assert status == 403
