data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

data "aws_cognito_user_pools" "existing" {
  name = "campuspulse-user-pool"
}

resource "aws_api_gateway_authorizer" "cognito" {
  name          = "campuspulse-cognito-authorizer"
  type          = "COGNITO_USER_POOLS"
  rest_api_id   = aws_api_gateway_rest_api.campus_api.id
  provider_arns = [data.aws_cognito_user_pools.existing.arns[0]]
}
