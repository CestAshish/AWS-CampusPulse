data "archive_file" "lambda_zip" {
  type        = "zip"
  source_dir  = "${path.module}/../src"
  output_path = "${path.module}/lambda.zip"
  # The simulator and its auth helper run on a laptop, not in Lambda.
  excludes = ["simulator.py", "auth.py"]
}

# Imported because Lambda created these log groups automatically on first run;
# managing them here lets us set a retention period instead of "never expire".
import {
  to = aws_cloudwatch_log_group.ingest
  id = "/aws/lambda/CampusPulse-Ingest"
}

import {
  to = aws_cloudwatch_log_group.stats
  id = "/aws/lambda/CampusPulse-Stats"
}

resource "aws_cloudwatch_log_group" "ingest" {
  name              = "/aws/lambda/CampusPulse-Ingest"
  retention_in_days = 14
}

resource "aws_cloudwatch_log_group" "stats" {
  name              = "/aws/lambda/CampusPulse-Stats"
  retention_in_days = 14
}

locals {
  lambda_vpc_config = var.lambda_in_vpc ? [{
    subnet_ids         = data.aws_subnets.private.ids
    security_group_ids = aws_security_group.lambda[*].id
  }] : []
  # Every route table used by the private subnets must route DynamoDB traffic
  # to the gateway endpoint, otherwise the Lambdas would time out.
  endpoint_covers_private_subnets = !var.lambda_in_vpc || length(setsubtract(local.private_route_table_ids, local.endpoint_route_table_ids)) == 0
}

resource "aws_lambda_function" "ingest" {
  filename         = data.archive_file.lambda_zip.output_path
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256
  function_name    = "CampusPulse-Ingest"
  description      = "POST /events: validates sensor events, detects anomalies, stores them in DynamoDB"
  role             = aws_iam_role.lambda_exec.arn
  handler          = "ingest_handler.lambda_handler"
  runtime          = "python3.12"
  timeout          = 15
  memory_size      = 256

  dynamic "vpc_config" {
    for_each = local.lambda_vpc_config
    content {
      subnet_ids         = vpc_config.value.subnet_ids
      security_group_ids = vpc_config.value.security_group_ids
    }
  }

  environment {
    variables = { TABLE_NAME = aws_dynamodb_table.events.name }
  }

  depends_on = [aws_cloudwatch_log_group.ingest, aws_iam_role_policy.lambda_policy]

  lifecycle {
    precondition {
      condition     = local.endpoint_covers_private_subnets
      error_message = "The DynamoDB gateway endpoint is not attached to every private route table. Attach it, set manage_dynamodb_endpoint = true, or set lambda_in_vpc = false."
    }
  }
}

resource "aws_lambda_function" "stats" {
  filename         = data.archive_file.lambda_zip.output_path
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256
  function_name    = "CampusPulse-Stats"
  description      = "GET /stats, /events, /alerts: aggregated read API for the dashboard"
  role             = aws_iam_role.lambda_exec.arn
  handler          = "stats_handler.lambda_handler"
  runtime          = "python3.12"
  timeout          = 15
  memory_size      = 256

  dynamic "vpc_config" {
    for_each = local.lambda_vpc_config
    content {
      subnet_ids         = vpc_config.value.subnet_ids
      security_group_ids = vpc_config.value.security_group_ids
    }
  }

  environment {
    variables = { TABLE_NAME = aws_dynamodb_table.events.name }
  }

  depends_on = [aws_cloudwatch_log_group.stats, aws_iam_role_policy.lambda_policy]

  lifecycle {
    precondition {
      condition     = local.endpoint_covers_private_subnets
      error_message = "The DynamoDB gateway endpoint is not attached to every private route table. Attach it, set manage_dynamodb_endpoint = true, or set lambda_in_vpc = false."
    }
  }
}
