resource "aws_dynamodb_table" "events" {
  name         = "CampusPulseEvents"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "building_id"
  range_key    = "timestamp"

  attribute {
    name = "building_id"
    type = "S"
  }
  attribute {
    name = "timestamp"
    type = "S"
  }
  attribute {
    name = "event_type"
    type = "S"
  }
  attribute {
    name = "alert_status"
    type = "S"
  }

  # Disaster recovery: continuous backups, restore to any second in the last 35 days.
  point_in_time_recovery {
    enabled = true
  }

  # Encryption at rest is always on: DynamoDB's default AWS owned key (no KMS cost).

  # Cost control: raw sensor events expire automatically after 30 days.
  ttl {
    attribute_name = "expires_at"
    enabled        = true
  }

  # Campus-wide queries by sensor type (GET /events?event_type=...).
  global_secondary_index {
    name            = "EventTypeIndex"
    hash_key        = "event_type"
    range_key       = "timestamp"
    projection_type = "ALL"
  }

  # Sparse index: only anomalous events carry alert_status, so GET /alerts
  # reads just the alerts instead of the whole table.
  global_secondary_index {
    name            = "AlertIndex"
    hash_key        = "alert_status"
    range_key       = "timestamp"
    projection_type = "ALL"
  }
}
