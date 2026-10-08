"""Read API for the dashboard: GET /stats, GET /events and GET /alerts."""
import os

import boto3
from boto3.dynamodb.conditions import Key

from common import (
    ALERT_PARTITION,
    BUILDINGS,
    EVENT_TYPES,
    READ_ROLES,
    is_allowed,
    response,
)

dynamodb = boto3.resource('dynamodb', region_name='eu-north-1')
table = dynamodb.Table(os.environ['TABLE_NAME'])

STATS_WINDOW = 300      # most recent events per building used for aggregates
RECENT_POINTS = 60      # raw events returned for the dashboard charts
CAMPUS_WINDOW = 60      # events per building used for the campus overview


def _limit(params, default=50, maximum=200):
    try:
        return max(1, min(int(params.get('limit', default)), maximum))
    except (TypeError, ValueError):
        return default


def latest_events(building_id, limit):
    """Newest-first query on the base table (PK building_id, SK timestamp)."""
    result = table.query(
        KeyConditionExpression=Key('building_id').eq(building_id),
        ScanIndexForward=False,
        Limit=limit,
    )
    return result.get('Items', [])


def summarise(items):
    """Aggregate readings per event type: latest, avg, min, max and anomalies."""
    summary = {}
    for event_type, spec in EVENT_TYPES.items():
        values = [float(i[spec['field']]) for i in items
                  if i.get('event_type') == event_type and spec['field'] in i]
        if not values:
            summary[event_type] = None
            continue
        summary[event_type] = {
            'latest': values[0],   # items are newest-first
            'avg': round(sum(values) / len(values), 2),
            'min': min(values),
            'max': max(values),
            'count': len(values),
            'unit': spec['unit'],
            'threshold': spec['alert_above'],
            'anomalies': sum(1 for v in values if v > spec['alert_above']),
        }
    return summary


def building_stats(building_id):
    items = latest_events(building_id, STATS_WINDOW)
    return {
        'building_id': building_id,
        'total_events': len(items),
        'window_events': STATS_WINDOW,
        'summary': summarise(items),
        'alerts': sum(1 for i in items if i.get('alert')),
        # Oldest-first so the dashboard can plot them directly.
        'data': list(reversed(items[:RECENT_POINTS])),
    }


def campus_stats():
    buildings = []
    for building_id in BUILDINGS:
        summary = summarise(latest_events(building_id, CAMPUS_WINDOW))
        buildings.append({'building_id': building_id, 'summary': summary})

    def latest(b, event_type):
        s = b['summary'][event_type]
        return s['latest'] if s else None

    with_energy = [b for b in buildings if latest(b, 'energy') is not None]
    return {
        'buildings': buildings,
        # Answers "which buildings consume the most energy?"
        'energy_ranking': [
            {'building_id': b['building_id'], 'avg_energy_kwh': b['summary']['energy']['avg']}
            for b in sorted(with_energy, key=lambda b: b['summary']['energy']['avg'], reverse=True)
        ],
        # Answers "which spaces are currently overloaded?"
        'overloaded': [
            {'building_id': b['building_id'], 'occupancy': latest(b, 'occupancy')}
            for b in buildings
            if latest(b, 'occupancy') is not None
            and latest(b, 'occupancy') > EVENT_TYPES['occupancy']['alert_above']
        ],
        'thresholds': {k: v['alert_above'] for k, v in EVENT_TYPES.items()},
    }


def list_events(params):
    limit = _limit(params)
    building_id = params.get('building_id')
    event_type = params.get('event_type')
    if event_type and event_type not in EVENT_TYPES:
        return response(400, {'error': f"event_type must be one of {sorted(EVENT_TYPES)}"})

    if building_id:
        items = latest_events(building_id, limit if not event_type else STATS_WINDOW)
        if event_type:
            items = [i for i in items if i.get('event_type') == event_type][:limit]
    else:
        types = [event_type] if event_type else list(EVENT_TYPES)
        items = []
        for t in types:
            items += table.query(
                IndexName='EventTypeIndex',
                KeyConditionExpression=Key('event_type').eq(t),
                ScanIndexForward=False,
                Limit=limit,
            ).get('Items', [])
        items = sorted(items, key=lambda i: i['timestamp'], reverse=True)[:limit]
    return response(200, {'count': len(items), 'events': items})


def list_alerts(params):
    items = table.query(
        IndexName='AlertIndex',
        KeyConditionExpression=Key('alert_status').eq(ALERT_PARTITION),
        ScanIndexForward=False,
        Limit=_limit(params),
    ).get('Items', [])
    return response(200, {'count': len(items), 'alerts': items})


def lambda_handler(event, context):
    if not is_allowed(event, READ_ROLES):
        return response(403, {'error': 'Only Admin or Staff accounts can read campus data'})

    params = event.get('queryStringParameters') or {}
    resource = event.get('resource') or event.get('path') or '/stats'
    try:
        if resource.endswith('/events'):
            return list_events(params)
        if resource.endswith('/alerts'):
            return list_alerts(params)
        if params.get('building_id'):
            return response(200, building_stats(params['building_id']))
        return response(200, campus_stats())
    except Exception as e:
        print(f"ERROR handling {resource}: {e}")
        return response(500, {'error': 'Internal error'})
