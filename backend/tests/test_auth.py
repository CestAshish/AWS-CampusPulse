import pytest
import boto3
from moto import mock_aws
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.auth import get_cognito_token, calculate_secret_hash

@pytest.fixture
def cognito_setup():
    """Sets up a mock Cognito User Pool and App Client for testing"""
    os.environ['AWS_ACCESS_KEY_ID'] = 'testing'
    os.environ['AWS_SECRET_ACCESS_KEY'] = 'testing'
    os.environ['AWS_DEFAULT_REGION'] = 'eu-north-1'
    
    with mock_aws():
        client = boto3.client('cognito-idp', region_name='eu-north-1')
        
        # Create mock User Pool
        pool_response = client.create_user_pool(PoolName='TestPool')
        pool_id = pool_response['UserPool']['Id']
        
        # Create mock App Client WITHOUT a secret (like Ebele's frontend)
        app_response = client.create_user_pool_client(
            UserPoolId=pool_id,
            ClientName='TestAppClient',
            GenerateSecret=False
        )
        client_id = app_response['UserPoolClient']['ClientId']
        
        # Create a mock user
        client.admin_create_user(
            UserPoolId=pool_id,
            Username='test_user@campuspulse.com',
            UserAttributes=[{'Name': 'email', 'Value': 'test_user@campuspulse.com'}],
            MessageAction='SUPPRESS'
        )
        # Set permanent password so we don't get a NEW_PASSWORD_REQUIRED challenge
        client.admin_set_user_password(
            UserPoolId=pool_id,
            Username='test_user@campuspulse.com',
            Password='@User123',
            Permanent=True
        )
        
        yield client_id

def test_auth_success_no_secret(cognito_setup):
    """Test that auth works for a Public Client (No Secret)"""
    client_id = cognito_setup
    
    token = get_cognito_token(
        username='test_user@campuspulse.com',
        password='@User123',
        client_id=client_id,
        client_secret=None
    )
    
    assert token is not None
    assert type(token) == str

def test_auth_wrong_password(cognito_setup):
    """Test that auth properly raises an exception for wrong passwords"""
    client_id = cognito_setup
    
    with pytest.raises(Exception) as excinfo:
        get_cognito_token(
            username='test_user@campuspulse.com',
            password='WrongPassword123',
            client_id=client_id,
            client_secret=None
        )
    
    assert "Cognito Error" in str(excinfo.value)
