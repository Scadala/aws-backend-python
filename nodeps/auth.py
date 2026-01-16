import json
import logging
import boto3
from botocore.exceptions import ClientError
from urllib.parse import urlencode

# Set up logging
logger = logging.getLogger(__name__)

client_id = "APP-6KSLC9TDGOYVUOTT"


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
