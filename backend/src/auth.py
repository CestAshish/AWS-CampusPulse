import os
import base64
import hashlib
import hmac
import boto3
from botocore.exceptions import ClientError

def calculate_secret_hash(username: str, client_id: str, client_secret: str) -> str:
    message = username + client_id
    digest = hmac.new(
        client_secret.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256
    ).digest()
    return base64.b64encode(digest).decode("utf-8")

def get_cognito_token(username, password, client_id, client_secret=None, region="eu-north-1"):
    """
    Authenticates against Cognito and returns the IdToken.
    Supports both Public App Clients (no secret) and Confidential App Clients (with secret).
    """
    client = boto3.client("cognito-idp", region_name=region)
    
    auth_params = {
        "USERNAME": username,
        "PASSWORD": password,
    }
    
    if client_secret:
        auth_params["SECRET_HASH"] = calculate_secret_hash(username, client_id, client_secret)
        
    try:
        response = client.initiate_auth(
            AuthFlow="USER_PASSWORD_AUTH",
            AuthParameters=auth_params,
            ClientId=client_id,
        )
        
        if "AuthenticationResult" in response:
            return response["AuthenticationResult"]["IdToken"]
        elif "ChallengeName" in response:
            raise Exception(f"Authentication challenge received: {response['ChallengeName']}. Please use the AWS Console to set a permanent password.")
            
    except ClientError as e:
        raise Exception(f"Cognito Error: {e.response['Error']['Message']}")
    except KeyError:
        raise Exception("Unexpected response from Cognito.")
