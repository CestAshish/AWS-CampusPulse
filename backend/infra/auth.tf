data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

resource "aws_api_gateway_authorizer" "cognito" {
  name          = "campuspulse-cognito-authorizer"
  type          = "COGNITO_USER_POOLS"
  rest_api_id   = aws_api_gateway_rest_api.campus_api.id
  provider_arns = ["arn:aws:cognito-idp:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:userpool/eu-north-1_hVIR8C6I5"]
}
