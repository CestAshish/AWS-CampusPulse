import os
import base64
import hashlib
import hmac

import boto3


REGION = "eu-north-1"

USERNAME = "test_user@campuspulse.com"
PASSWORD = "@User123"
CLIENT_ID = os.environ["COGNITO_CLIENT_ID"]
CLIENT_SECRET = os.environ["COGNITO_CLIENT_SECRET"]


def calculate_secret_hash(username, client_id, client_secret):
    message = username + client_id

    digest = hmac.new(
        client_secret.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256
    ).digest()

    return base64.b64encode(digest).decode("utf-8")


secret_hash = calculate_secret_hash(
    USERNAME,
    CLIENT_ID,
    CLIENT_SECRET
)


client = boto3.client(
    "cognito-idp",
    region_name=REGION
)


response = client.initiate_auth(
    AuthFlow="USER_PASSWORD_AUTH",
    AuthParameters={
        "USERNAME": USERNAME,
        "PASSWORD": PASSWORD,
        "SECRET_HASH": secret_hash,
    },
    ClientId=CLIENT_ID,
)


print("Cognito response:")
print(response)

if "AuthenticationResult" in response:
    id_token = response["AuthenticationResult"]["IdToken"]

    print("\nAuthentication successful!")
    print("\nIdToken:")
    print(id_token)

elif "ChallengeName" in response:
    print("\nAuthentication challenge received:")
    print(response["ChallengeName"])

else:
    print("\nUnexpected Cognito response.")