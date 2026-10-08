# Thresholds must match EVENT_TYPES in backend/src/common.py and the dashboard.
locals {
  sensor_alarms = {
    HighTemperature = { metric = "Temperature", threshold = 28, description = "A building temperature exceeded 28 C" }
    HighOccupancy   = { metric = "OccupancyCount", threshold = 150, description = "A building exceeded its 150-person capacity (fire code warning)" }
    HighEnergy      = { metric = "EnergyUsage", threshold = 120, description = "Energy usage exceeded 120 kWh (power surge warning)" }
  }
  lambda_functions = {
    Ingest = aws_lambda_function.ingest.function_name
    Stats  = aws_lambda_function.stats.function_name
  }
  # Custom metrics are emitted by the ingest Lambda (Embedded Metric Format).
  metric_dimensions = { Service = "CampusPulse" }
}

# 1. SNS topic for every alarm
resource "aws_sns_topic" "alerts" {
  name = "campuspulse-alerts"
}

# 2. Email subscription (must be confirmed from the inbox once)
resource "aws_sns_topic_subscription" "email_alert" {
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

# 3. Platform health: API Gateway 5xx errors
resource "aws_cloudwatch_metric_alarm" "api_errors" {
  alarm_name          = "CampusPulse-HighAPIErrorRate"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "5XXError"
  namespace           = "AWS/ApiGateway"
  period              = 300
  statistic           = "Sum"
  threshold           = 5
  treat_missing_data  = "notBreaching"
  alarm_description   = "More than 5 server errors in 5 minutes on the CampusPulse API"
  alarm_actions       = [aws_sns_topic.alerts.arn]

  dimensions = {
    ApiName = aws_api_gateway_rest_api.campus_api.name
  }
}

# 4. Platform health: Lambda errors and throttles
resource "aws_cloudwatch_metric_alarm" "lambda_errors" {
  for_each            = local.lambda_functions
  alarm_name          = "CampusPulse-${each.key}-Errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = 300
  statistic           = "Sum"
  threshold           = 0
  treat_missing_data  = "notBreaching"
  alarm_description   = "The ${each.value} function raised an error"
  alarm_actions       = [aws_sns_topic.alerts.arn]
  dimensions          = { FunctionName = each.value }
}

resource "aws_cloudwatch_metric_alarm" "lambda_throttles" {
  for_each            = local.lambda_functions
  alarm_name          = "CampusPulse-${each.key}-Throttles"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "Throttles"
  namespace           = "AWS/Lambda"
  period              = 300
  statistic           = "Sum"
  threshold           = 0
  treat_missing_data  = "notBreaching"
  alarm_description   = "The ${each.value} function is being throttled (concurrency limit reached)"
  alarm_actions       = [aws_sns_topic.alerts.arn]
  dimensions          = { FunctionName = each.value }
}

# 5. Campus anomalies: sensor readings above the safety thresholds
resource "aws_cloudwatch_metric_alarm" "high_temperature" {
  alarm_name          = "CampusPulse-HighTemperature"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = local.sensor_alarms.HighTemperature.metric
  namespace           = "CampusPulse"
  period              = 60
  statistic           = "Maximum"
  threshold           = local.sensor_alarms.HighTemperature.threshold
  treat_missing_data  = "notBreaching"
  alarm_description   = local.sensor_alarms.HighTemperature.description
  alarm_actions       = [aws_sns_topic.alerts.arn]
  dimensions          = local.metric_dimensions
}

resource "aws_cloudwatch_metric_alarm" "high_occupancy" {
  alarm_name          = "CampusPulse-HighOccupancy"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = local.sensor_alarms.HighOccupancy.metric
  namespace           = "CampusPulse"
  period              = 60
  statistic           = "Maximum"
  threshold           = local.sensor_alarms.HighOccupancy.threshold
  treat_missing_data  = "notBreaching"
  alarm_description   = local.sensor_alarms.HighOccupancy.description
  alarm_actions       = [aws_sns_topic.alerts.arn]
  dimensions          = local.metric_dimensions
}

resource "aws_cloudwatch_metric_alarm" "high_energy" {
  alarm_name          = "CampusPulse-HighEnergy"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = local.sensor_alarms.HighEnergy.metric
  namespace           = "CampusPulse"
  period              = 60
  statistic           = "Maximum"
  threshold           = local.sensor_alarms.HighEnergy.threshold
  treat_missing_data  = "notBreaching"
  alarm_description   = local.sensor_alarms.HighEnergy.description
  alarm_actions       = [aws_sns_topic.alerts.arn]
  dimensions          = local.metric_dimensions
}

# 6. Operations dashboard (CloudWatch free tier: 3 dashboards)
resource "aws_cloudwatch_dashboard" "main" {
  dashboard_name = "CampusPulse-Monitoring"
  dashboard_body = jsonencode({
    widgets = [
      {
        type = "metric", x = 0, y = 0, width = 12, height = 6
        properties = {
          title  = "API Gateway: requests and errors"
          region = "eu-north-1"
          stat   = "Sum"
          period = 60
          metrics = [
            ["AWS/ApiGateway", "Count", "ApiName", aws_api_gateway_rest_api.campus_api.name],
            [".", "4XXError", ".", "."],
            [".", "5XXError", ".", "."]
          ]
        }
      },
      {
        type = "metric", x = 12, y = 0, width = 12, height = 6
        properties = {
          title  = "API Gateway: latency (ms)"
          region = "eu-north-1"
          period = 60
          metrics = [
            ["AWS/ApiGateway", "Latency", "ApiName", aws_api_gateway_rest_api.campus_api.name, { stat = "Average" }],
            ["...", { stat = "p95" }]
          ]
        }
      },
      {
        type = "metric", x = 0, y = 6, width = 12, height = 6
        properties = {
          title  = "Lambda: invocations, errors, throttles"
          region = "eu-north-1"
          stat   = "Sum"
          period = 60
          metrics = concat(
            [for name in values(local.lambda_functions) : ["AWS/Lambda", "Invocations", "FunctionName", name]],
            [for name in values(local.lambda_functions) : ["AWS/Lambda", "Errors", "FunctionName", name]],
            [for name in values(local.lambda_functions) : ["AWS/Lambda", "Throttles", "FunctionName", name]]
          )
        }
      },
      {
        type = "metric", x = 12, y = 6, width = 12, height = 6
        properties = {
          title  = "Lambda: duration (ms)"
          region = "eu-north-1"
          stat   = "Average"
          period = 60
          metrics = [for name in values(local.lambda_functions) : ["AWS/Lambda", "Duration", "FunctionName", name]]
        }
      },
      {
        type = "metric", x = 0, y = 12, width = 8, height = 6
        properties = {
          title       = "Temperature (C), max per minute"
          region      = "eu-north-1"
          stat        = "Maximum"
          period      = 60
          metrics     = [["CampusPulse", "Temperature", "Service", "CampusPulse"]]
          annotations = { horizontal = [{ label = "Alert", value = 28 }] }
        }
      },
      {
        type = "metric", x = 8, y = 12, width = 8, height = 6
        properties = {
          title       = "Occupancy (people), max per minute"
          region      = "eu-north-1"
          stat        = "Maximum"
          period      = 60
          metrics     = [["CampusPulse", "OccupancyCount", "Service", "CampusPulse"]]
          annotations = { horizontal = [{ label = "Capacity", value = 150 }] }
        }
      },
      {
        type = "metric", x = 16, y = 12, width = 8, height = 6
        properties = {
          title       = "Energy (kWh), max per minute"
          region      = "eu-north-1"
          stat        = "Maximum"
          period      = 60
          metrics     = [["CampusPulse", "EnergyUsage", "Service", "CampusPulse"]]
          annotations = { horizontal = [{ label = "Surge", value = 120 }] }
        }
      },
      {
        type = "metric", x = 0, y = 18, width = 12, height = 6
        properties = {
          title   = "Anomalies detected per minute"
          region  = "eu-north-1"
          stat    = "Sum"
          period  = 60
          metrics = [["CampusPulse", "AnomalyCount", "Service", "CampusPulse"]]
        }
      },
      {
        type = "metric", x = 12, y = 18, width = 12, height = 6
        properties = {
          title  = "DynamoDB: consumed capacity"
          region = "eu-north-1"
          stat   = "Sum"
          period = 60
          metrics = [
            ["AWS/DynamoDB", "ConsumedWriteCapacityUnits", "TableName", aws_dynamodb_table.events.name],
            [".", "ConsumedReadCapacityUnits", ".", "."]
          ]
        }
      },
      {
        type = "log", x = 0, y = 24, width = 24, height = 6
        properties = {
          title  = "Recent Lambda errors (troubleshooting)"
          region = "eu-north-1"
          view   = "table"
          query  = "SOURCE '${aws_cloudwatch_log_group.ingest.name}' | SOURCE '${aws_cloudwatch_log_group.stats.name}' | fields @timestamp, @log, @message | filter @message like /ERROR|Task timed out/ | sort @timestamp desc | limit 20"
        }
      }
    ]
  })
}

output "dashboard_url" {
  value = "https://eu-north-1.console.aws.amazon.com/cloudwatch/home?region=eu-north-1#dashboards:name=${aws_cloudwatch_dashboard.main.dashboard_name}"
}
