import os
import sys
import json
import pytest
import boto3
from moto import mock_aws

import importlib

# Add parent directory to python path so we can import src
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

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

@pytest.fixture
def dynamodb_mock():
    with mock_aws():
        # Reload modules inside the mock context so boto3 clients are mocked
        importlib.reload(ingest_handler)
        importlib.reload(stats_handler)
        
        dynamodb = boto3.resource('dynamodb', region_name='eu-north-1')
        # Create a fake DynamoDB table just for testing
        table = dynamodb.create_table(
            TableName='CampusPulseEvents',
            KeySchema=[
                {'AttributeName': 'building_id', 'KeyType': 'HASH'},
                {'AttributeName': 'timestamp', 'KeyType': 'RANGE'}
            ],
            AttributeDefinitions=[
                {'AttributeName': 'building_id', 'AttributeType': 'S'},
                {'AttributeName': 'timestamp', 'AttributeType': 'S'},
                {'AttributeName': 'event_type', 'AttributeType': 'S'}
            ],
            BillingMode='PAY_PER_REQUEST',
            GlobalSecondaryIndexes=[{
                'IndexName': 'EventTypeIndex',
                'KeySchema': [
                    {'AttributeName': 'event_type', 'KeyType': 'HASH'},
                    {'AttributeName': 'timestamp', 'KeyType': 'RANGE'}
                ],
                'Projection': {'ProjectionType': 'ALL'}
            }]
        )
        yield table

def test_ingest_handler_success(dynamodb_mock):
    """Test that the ingest handler correctly saves JSON to DynamoDB"""
    event = {
        'body': json.dumps({
            'building_id': 'BLDG-A',
            'event_type': 'occupancy',
            'occupancy_count': 42
        })
    }
    
    # 1. Trigger the Lambda function
    response = ingest_handler.lambda_handler(event, None)
    
    # 2. Check that Lambda returned 201 Created
    assert response['statusCode'] == 201
    assert 'successfully' in response['body']
    
    # 3. Check the database to make sure the data actually got written
    db_response = dynamodb_mock.scan()
    items = db_response['Items']
    assert len(items) == 1
    assert items[0]['building_id'] == 'BLDG-A'
    assert items[0]['occupancy_count'] == 42
    assert items[0]['event_type'] == 'occupancy'
    assert 'timestamp' in items[0]  # Ensure timestamp was auto-generated

def test_stats_handler_success(dynamodb_mock):
    """Test that the stats handler correctly fetches data from DynamoDB"""
    
    # 1. Pre-fill the fake database with some test data
    dynamodb_mock.put_item(Item={
        'building_id': 'BLDG-A',
        'timestamp': '2026-08-19T10:00:00',
        'event_type': 'temperature',
        'temperature_c': '22.5'
    })
    dynamodb_mock.put_item(Item={
        'building_id': 'BLDG-A',
        'timestamp': '2026-08-19T10:05:00',
        'event_type': 'occupancy',
        'occupancy_count': 100
    })
    
    # 2. Trigger the stats Lambda (like a GET request)
    event = {
        'queryStringParameters': {'building_id': 'BLDG-A'}
    }
    
    response = stats_handler.lambda_handler(event, None)
    
    # 3. Check that it successfully returned our 2 records
    assert response['statusCode'] == 200
    body = json.loads(response['body'])
    assert body['total_events'] == 2
    assert body['building_id'] == 'BLDG-A'
    assert len(body['data']) == 2
