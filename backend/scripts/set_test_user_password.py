import os
import boto3


REGION = "eu-north-1"

USER_POOL_ID = os.environ["COGNITO_USER_POOL_ID"]
USERNAME = os.environ.get("COGNITO_USERNAME", "test_user@campuspulse.com")
PASSWORD = os.environ["COGNITO_PASSWORD"]  # never commit real passwords


client = boto3.client(
    "cognito-idp",
    region_name=REGION
)


response = client.admin_set_user_password(
    UserPoolId=USER_POOL_ID,
    Username=USERNAME,
    Password=PASSWORD,
    Permanent=True,
)

print("Test user's password has been set permanently.")