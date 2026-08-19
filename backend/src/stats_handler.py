import json
import os
import boto3
from boto3.dynamodb.conditions import Key

dynamodb = boto3.resource('dynamodb', region_name='eu-north-1')
table = dynamodb.Table(os.environ['TABLE_NAME'])

def lambda_handler(event, context):
    try:
        query_params = event.get('queryStringParameters') or {}
        building_id = query_params.get('building_id', 'BLDG-A')
        
        response = table.query(
            KeyConditionExpression=Key('building_id').eq(building_id)
        )
        
        return {
            'statusCode': 200,
            'headers': {'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({
                'building_id': building_id,
                'total_events': len(response.get('Items', [])),
                'data': response.get('Items', [])
            })
        }
    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }
