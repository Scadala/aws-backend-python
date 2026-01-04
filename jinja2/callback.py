import json
import logging
import boto3
from botocore.exceptions import ClientError
from urllib.parse import urlencode, quote_plus
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

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
    """Lambda function to handle OAuth 2.0 callback from ORCID

    Parameters
    ----------
    event: dict, required
        API Gateway Lambda Proxy Input Format (v2)

    context: object, required
        Lambda Context runtime methods and attributes

    Returns
    ------
    API Gateway Lambda Proxy Output Format (v2): dict
        Returns a 302 redirect to root path with session cookies set
    """
    logger.info("Callback received", extra={"event": event})
    
    # Get the authorization code from query parameters
    query_params = event.get('queryStringParameters', {})
    if not query_params:
        logger.error("No query parameters found")
        return {
            "statusCode": 400,
            "body": "Missing authorization code"
        }
    
    code = query_params.get('code')
    if not code:
        logger.error("No authorization code found")
        return {
            "statusCode": 400,
            "body": "Missing authorization code"
        }
    
    # Get ORCID client credentials
    credentials = get_orcid_credentials()
    client_id = credentials.get('id')
    client_secret = credentials.get('secret')
    
    # Build the redirect URI (same as in auth.py)
    domain = event.get('requestContext', {}).get('domainName', '')
    stage = event.get('requestContext', {}).get('stage', '')
    
    if stage and stage != '$default':
        redirect_uri = f"https://{domain}/{stage}/callback"
    else:
        redirect_uri = f"https://{domain}/callback"
    
    # Exchange code for access token
    token_url = 'https://orcid.org/oauth/token'
    token_data = {
        'client_id': client_id,
        'client_secret': client_secret,
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': redirect_uri
    }
    
    logger.info(f"Exchanging code for token at {token_url}")
    
    try:
        # Encode the POST data
        data = urlencode(token_data).encode('utf-8')
        
        # Create the request
        request = Request(
            token_url,
            data=data,
            headers={
                'Accept': 'application/json',
                'Content-Type': 'application/x-www-form-urlencoded'
            }
        )
        
        # Make the POST request
        with urlopen(request) as response:
            response_data = response.read().decode('utf-8')
            token_response = json.loads(response_data)
        
        logger.info(f"Token exchange successful for ORCID: {token_response.get('orcid', 'unknown')}")
        
        # Extract user information from the token response
        name = token_response.get('name', 'ORCID User')
        orcid = token_response.get('orcid', '')
        
        # Create session cookies with URL-encoded values
        cookies = [
            f"name={quote_plus(name)}",
            f"orcid={quote_plus(orcid)}"
        ]
        
        # Redirect to root path
        return {
            "statusCode": 302,
            "headers": {
                "Location": "/"
            },
            "cookies": cookies
        }
        
    except (HTTPError, URLError) as e:
        logger.error(f"Error exchanging code for token: {e}")
        return {
            "statusCode": 500,
            "body": f"Error during authentication: {str(e)}"
        }
