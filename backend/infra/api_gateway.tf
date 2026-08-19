resource "aws_api_gateway_rest_api" "campus_api" {
  name        = "CampusPulse-API"
  description = "Public endpoint for IoT events"
  endpoint_configuration { types = ["REGIONAL"] }
}
