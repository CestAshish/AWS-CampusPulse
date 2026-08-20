resource "aws_dynamodb_table" "events" {
  name           = "CampusPulseEvents"
  billing_mode   = "PAY_PER_REQUEST"
  hash_key       = "building_id"
  range_key      = "timestamp"

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

  global_secondary_index {
    name               = "EventTypeIndex"
    hash_key           = "event_type"
    range_key          = "timestamp"
    projection_type    = "ALL"
  }
}
