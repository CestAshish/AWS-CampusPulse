import json
import os
import boto3
from datetime import datetime

dynamodb = boto3.resource('dynamodb', region_name='eu-north-1')
cloudwatch = boto3.client('cloudwatch', region_name='eu-north-1')
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

        cloudwatch.put_metric_data(
            Namespace='CampusPulse',
            MetricData=[
                {
                    'MetricName': 'OccupancyCount',
                    'Value': body.get('occupancy_count', 0),
                    'Unit': 'Count'
                },
                {
                    'MetricName': 'Temperature',
                    'Value': body.get('temperature_c', 0),
                    'Unit': 'None'
                },
                {
                    'MetricName': 'EnergyUsage',
                    'Value': body.get('energy_kwh', 0),
                    'Unit': 'None'
                }
            ]
        )
        
        return {
            'statusCode': 201,
            'body': json.dumps({'message': 'Event ingested successfully'})
        }
    except Exception as e:
        return {
            'statusCode': 400,
            'body': json.dumps({'error': str(e)})
        }
