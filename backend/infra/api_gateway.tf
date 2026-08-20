resource "aws_api_gateway_rest_api" "campus_api" {
  name        = "CampusPulse-API"
  description = "Public endpoint for IoT events"
  endpoint_configuration {
    types = ["REGIONAL"]
  }
}

# --- EVENTS ROUTE (POST /events) ---
resource "aws_api_gateway_resource" "events" {
  rest_api_id = aws_api_gateway_rest_api.campus_api.id
  parent_id   = aws_api_gateway_rest_api.campus_api.root_resource_id
  path_part   = "events"
}

resource "aws_api_gateway_method" "events_post" {
  rest_api_id   = aws_api_gateway_rest_api.campus_api.id
  resource_id   = aws_api_gateway_resource.events.id
  http_method   = "POST"
  authorization = "NONE" # We will add Cognito soon!
}

resource "aws_api_gateway_integration" "events_lambda" {
  rest_api_id             = aws_api_gateway_rest_api.campus_api.id
  resource_id             = aws_api_gateway_resource.events.id
  http_method             = aws_api_gateway_method.events_post.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.ingest.invoke_arn
}

resource "aws_lambda_permission" "events_apigw" {
  statement_id  = "AllowAPIGatewayInvokeEvents"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.ingest.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.campus_api.execution_arn}/*/*"
}

# --- STATS ROUTE (GET /stats) ---
resource "aws_api_gateway_resource" "stats" {
  rest_api_id = aws_api_gateway_rest_api.campus_api.id
  parent_id   = aws_api_gateway_rest_api.campus_api.root_resource_id
  path_part   = "stats"
}

resource "aws_api_gateway_method" "stats_get" {
  rest_api_id   = aws_api_gateway_rest_api.campus_api.id
  resource_id   = aws_api_gateway_resource.stats.id
  http_method   = "GET"
  authorization = "NONE" # We will add Cognito soon!
}

resource "aws_api_gateway_integration" "stats_lambda" {
  rest_api_id             = aws_api_gateway_rest_api.campus_api.id
  resource_id             = aws_api_gateway_resource.stats.id
  http_method             = aws_api_gateway_method.stats_get.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.stats.invoke_arn
}

resource "aws_lambda_permission" "stats_apigw" {
  statement_id  = "AllowAPIGatewayInvokeStats"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.stats.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.campus_api.execution_arn}/*/*"
}

# --- DEPLOYMENT ---
resource "aws_api_gateway_deployment" "prod" {
  rest_api_id = aws_api_gateway_rest_api.campus_api.id
  depends_on = [
    aws_api_gateway_integration.events_lambda,
    aws_api_gateway_integration.stats_lambda
  ]
}

resource "aws_api_gateway_stage" "prod" {
  deployment_id = aws_api_gateway_deployment.prod.id
  rest_api_id   = aws_api_gateway_rest_api.campus_api.id
  stage_name    = "prod"
}

output "api_url" {
  value = aws_api_gateway_stage.prod.invoke_url
}
