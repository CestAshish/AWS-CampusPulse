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
  authorization = "COGNITO_USER_POOLS"
  authorizer_id = aws_api_gateway_authorizer.cognito.id
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
  authorization = "COGNITO_USER_POOLS"
  authorizer_id = aws_api_gateway_authorizer.cognito.id
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
  description = "Trigger deployment for Cognito Security Lock"
  depends_on = [
    aws_api_gateway_integration.events_lambda,
    aws_api_gateway_integration.stats_lambda,
    aws_api_gateway_integration.events_options_integration,
    aws_api_gateway_integration.stats_options_integration
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
# --- CORS OPTIONS FOR /events ---
resource "aws_api_gateway_method" "events_options" {
  rest_api_id   = aws_api_gateway_rest_api.campus_api.id
  resource_id   = aws_api_gateway_resource.events.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "events_options_integration" {
  rest_api_id = aws_api_gateway_rest_api.campus_api.id
  resource_id = aws_api_gateway_resource.events.id
  http_method = aws_api_gateway_method.events_options.http_method
  type        = "MOCK"
  request_templates = { "application/json" = "{\"statusCode\": 200}" }
}

resource "aws_api_gateway_method_response" "events_options_200" {
  rest_api_id = aws_api_gateway_rest_api.campus_api.id
  resource_id = aws_api_gateway_resource.events.id
  http_method = aws_api_gateway_method.events_options.http_method
  status_code = "200"
  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = true,
    "method.response.header.Access-Control-Allow-Methods" = true,
    "method.response.header.Access-Control-Allow-Origin"  = true
  }
}

resource "aws_api_gateway_integration_response" "events_options_integration_response" {
  rest_api_id = aws_api_gateway_rest_api.campus_api.id
  resource_id = aws_api_gateway_resource.events.id
  http_method = aws_api_gateway_method.events_options.http_method
  status_code = aws_api_gateway_method_response.events_options_200.status_code
  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,Authorization'",
    "method.response.header.Access-Control-Allow-Methods" = "'OPTIONS,POST,GET'",
    "method.response.header.Access-Control-Allow-Origin"  = "'*'"
  }
  depends_on = [aws_api_gateway_integration.events_options_integration]
}

# --- CORS OPTIONS FOR /stats ---
resource "aws_api_gateway_method" "stats_options" {
  rest_api_id   = aws_api_gateway_rest_api.campus_api.id
  resource_id   = aws_api_gateway_resource.stats.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "stats_options_integration" {
  rest_api_id = aws_api_gateway_rest_api.campus_api.id
  resource_id = aws_api_gateway_resource.stats.id
  http_method = aws_api_gateway_method.stats_options.http_method
  type        = "MOCK"
  request_templates = { "application/json" = "{\"statusCode\": 200}" }
}

resource "aws_api_gateway_method_response" "stats_options_200" {
  rest_api_id = aws_api_gateway_rest_api.campus_api.id
  resource_id = aws_api_gateway_resource.stats.id
  http_method = aws_api_gateway_method.stats_options.http_method
  status_code = "200"
  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = true,
    "method.response.header.Access-Control-Allow-Methods" = true,
    "method.response.header.Access-Control-Allow-Origin"  = true
  }
}

resource "aws_api_gateway_integration_response" "stats_options_integration_response" {
  rest_api_id = aws_api_gateway_rest_api.campus_api.id
  resource_id = aws_api_gateway_resource.stats.id
  http_method = aws_api_gateway_method.stats_options.http_method
  status_code = aws_api_gateway_method_response.stats_options_200.status_code
  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,Authorization'",
    "method.response.header.Access-Control-Allow-Methods" = "'OPTIONS,POST,GET'",
    "method.response.header.Access-Control-Allow-Origin"  = "'*'"
  }
  depends_on = [aws_api_gateway_integration.stats_options_integration]
}
resource "aws_api_gateway_gateway_response" "default_4xx" {
  rest_api_id   = aws_api_gateway_rest_api.campus_api.id
  response_type = "DEFAULT_4XX"

  response_parameters = {
    "gatewayresponse.header.Access-Control-Allow-Origin"  = "'*'"
    "gatewayresponse.header.Access-Control-Allow-Headers" = "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'"
    "gatewayresponse.header.Access-Control-Allow-Methods" = "'GET,OPTIONS,POST,PUT,PATCH,DELETE'"
  }
}

resource "aws_api_gateway_gateway_response" "default_5xx" {
  rest_api_id   = aws_api_gateway_rest_api.campus_api.id
  response_type = "DEFAULT_5XX"

  response_parameters = {
    "gatewayresponse.header.Access-Control-Allow-Origin"  = "'*'"
    "gatewayresponse.header.Access-Control-Allow-Headers" = "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'"
    "gatewayresponse.header.Access-Control-Allow-Methods" = "'GET,OPTIONS,POST,PUT,PATCH,DELETE'"
  }
}
