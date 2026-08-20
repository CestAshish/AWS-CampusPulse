import json
import os
import boto3
from datetime import datetime

dynamodb = boto3.resource('dynamodb', region_name='eu-north-1')
table = dynamodb.Table(os.environ['TABLE_NAME'])

def lambda_handler(event, context):
    try:
        body = json.loads(event.get('body', '{}'))
        
        item = {
            'building_id': body['building_id'],
            'timestamp': body.get('timestamp', datetime.utcnow().isoformat()),
            'event_type': body['event_type'],
            'occupancy_count': body.get('occupancy_count', 0),
            'temperature_c': str(body.get('temperature_c', 0)),
            'energy_kwh': str(body.get('energy_kwh', 0)),
            'alert': body.get('alert', False)
        }
        
        table.put_item(Item=item)
        
        return {
            'statusCode': 201,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type,Authorization',
                'Access-Control-Allow-Methods': 'OPTIONS,POST,GET'
            },
            'body': json.dumps({'message': 'Event ingested successfully'})
        }
    except Exception as e:
        return {
            'statusCode': 400,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type,Authorization',
                'Access-Control-Allow-Methods': 'OPTIONS,POST,GET'
            },
            'body': json.dumps({'error': str(e)})
        }
