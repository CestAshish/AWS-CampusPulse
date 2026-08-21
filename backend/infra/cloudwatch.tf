# 1. Create the SNS Topic
resource "aws_sns_topic" "alerts" {
  name = "campuspulse-alerts"
}

# 2. Subscribe your email to the SNS Topic
resource "aws_sns_topic_subscription" "email_alert" {
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = "ashish.singh@epita.fr"
}

# 3. Alarm: High API Gateway 5xx Errors
resource "aws_cloudwatch_metric_alarm" "api_errors" {
  alarm_name          = "CampusPulse-HighAPIErrorRate"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "5XXError"
  namespace           = "AWS/ApiGateway"
  period              = 300
  statistic           = "Sum"
  threshold           = 5
  alarm_description   = "Triggers if the API Gateway has too many server errors"
  alarm_actions       = [aws_sns_topic.alerts.arn]
  
  dimensions = {
    ApiName = aws_api_gateway_rest_api.campus_api.name
  }
}

# 4. Alarm: High Temperature Alert
resource "aws_cloudwatch_metric_alarm" "high_temperature" {
  alarm_name          = "CampusPulse-HighTemperature"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "Temperature"
  namespace           = "CampusPulse"
  period              = 60
  statistic           = "Maximum"
  threshold           = 25.0
  alarm_description   = "Triggers if any building temperature exceeds 25.0°C"
  alarm_actions       = [aws_sns_topic.alerts.arn]
}

# 5. Alarm: High Occupancy Alert
resource "aws_cloudwatch_metric_alarm" "high_occupancy" {
  alarm_name          = "CampusPulse-HighOccupancy"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "OccupancyCount"
  namespace           = "CampusPulse"
  period              = 60
  statistic           = "Maximum"
  threshold           = 450.0
  alarm_description   = "Triggers if building occupancy exceeds 450 people (Fire code warning)"
  alarm_actions       = [aws_sns_topic.alerts.arn]
}

# 6. Alarm: High Energy Alert
resource "aws_cloudwatch_metric_alarm" "high_energy" {
  alarm_name          = "CampusPulse-HighEnergy"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "EnergyUsage"
  namespace           = "CampusPulse"
  period              = 60
  statistic           = "Maximum"
  threshold           = 90.0
  alarm_description   = "Triggers if energy usage exceeds 90.0 kWh (Power surge warning)"
  alarm_actions       = [aws_sns_topic.alerts.arn]
}
