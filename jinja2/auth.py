import json
import logging
import boto3
from botocore.exceptions import ClientError
from urllib.parse import urlencode

# Set up logging
logger = logging.getLogger(__name__)

# Initialize AWS Secrets Manager client
secrets_client = boto3.client('secretsmanager', region_name='eu-central-1')

def get_orcid_credentials():
    """Retrieve ORCID credentials from AWS Secrets Manager"""
    secret_arn = 'arn:aws:secretsmanager:eu-central-1:796401245269:secret:orcid-Z2L4Nt'
    try:
        response = secrets_client.get_secret_value(SecretId=secret_arn)
        secret = json.loads(response['SecretString'])
        return secret
    except ClientError as e:
        logger.error(f"Error retrieving secret: {e}")
        raise

def lambda_handler(event, context):
    """Lambda function to initiate OAuth 2.0 flow with ORCID

    Parameters
    ----------
    event: dict, required
        API Gateway Lambda Proxy Input Format (v2)

    context: object, required
        Lambda Context runtime methods and attributes

    Returns
    ------
    API Gateway Lambda Proxy Output Format (v2): dict
        Returns a 302 redirect to ORCID authorization URL
    """
    logger.info("Auth flow started", extra={"event": event})
    
    # Get ORCID client credentials
    credentials = get_orcid_credentials()
    client_id = credentials.get('client_id')
    
    # Build the redirect URI
    # Extract the domain from the request context
    domain = event.get('requestContext', {}).get('domainName', '')
    stage = event.get('requestContext', {}).get('stage', '')
    
    # Construct the callback URL
    if stage and stage != '$default':
        redirect_uri = f"https://{domain}/{stage}/callback"
    else:
        redirect_uri = f"https://{domain}/callback"
    
    # Build ORCID authorization URL
    auth_params = {
        'client_id': client_id,
        'response_type': 'code',
        'scope': '/authenticate',
        'redirect_uri': redirect_uri
    }
    
    auth_url = f"https://orcid.org/oauth/authorize?{urlencode(auth_params)}"
    
    logger.info(f"Redirecting to ORCID: {auth_url}")
    
    return {
        "statusCode": 302,
        "headers": {
            "Location": auth_url
        }
    }
