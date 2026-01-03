import os
import logging
from jinja2 import Environment, FileSystemLoader
from datetime import datetime, timedelta
from urllib.parse import quote, unquote

# Set up logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Constants
COOKIE_EXPIRATION_DAYS = 365

# Set up Jinja2 environment to load templates from the templates directory
template_dir = os.path.join(os.path.dirname(__file__), 'templates')
jinja_env = Environment(loader=FileSystemLoader(template_dir))

# Load the template once at module initialization for better performance
template = jinja_env.get_template('index.html')

def parse_cookies(cookie_header):
    """Parse cookies from Cookie header string
    
    Parameters
    ----------
    cookie_header: str
        The Cookie header value
    
    Returns
    -------
    dict
        Dictionary of cookie name-value pairs
    """
    cookies = {}
    if cookie_header:
        for cookie in cookie_header.split(';'):
            cookie = cookie.strip()
            if '=' in cookie:
                name, value = cookie.split('=', 1)
                cookies[name.strip()] = value.strip()
    return cookies

def lambda_handler(event, context):
    """Sample Lambda function which returns an HTML response rendered by Jinja2

    Parameters
    ----------
    event: dict, required
        API Gateway Lambda Proxy Input Format (v2)

        Event doc: https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-develop-integrations-lambda.html

    context: object, required
        Lambda Context runtime methods and attributes

        Context doc: https://docs.aws.amazon.com/lambda/latest/dg/python-context-object.html

    Returns
    ------
    API Gateway Lambda Proxy Output Format (v2): dict

        Return doc: https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-develop-integrations-lambda.html
    """

    # Get cookies from the request
    headers = event.get('headers', {})
    # Handle case-insensitive header lookup by creating a lowercase key mapping
    # In API Gateway v2, headers can be None
    if headers is None:
        headers = {}
    headers_lower = {k.lower(): v for k, v in headers.items()}
    cookie_header = headers_lower.get('cookie', '')
    cookies = parse_cookies(cookie_header)
    
    # Get current time
    current_time = datetime.utcnow()
    
    # Parse visit counter with error handling
    try:
        visits = int(cookies.get('visits', 0))
    except (ValueError, TypeError):
        visits = 0
    
    # Parse last visit timestamp with error handling and validation
    last_visit_str = unquote(cookies.get('last_visit', ''))
    last_visit = 'Never'
    if last_visit_str:
        try:
            # Validate the format by parsing - result is discarded as we only need validation
            datetime.strptime(last_visit_str, '%Y-%m-%d %H:%M:%S')
            last_visit = last_visit_str
        except ValueError:
            pass  # Keep last_visit as 'Never'
    
    # Increment visits
    visits += 1
    
    # Update last_visit to current time
    current_time_str = current_time.strftime('%Y-%m-%d %H:%M:%S')
    
    # Render the template with visit information
    html_content = template.render(
        message="Hello World",
        visits=visits,
        last_visit=last_visit
    )
    
    # Set cookie expiration (1 year from now)
    expires = (current_time + timedelta(days=COOKIE_EXPIRATION_DAYS)).strftime('%a, %d %b %Y %H:%M:%S GMT')
    
    return {
        "statusCode": 200,
        "body": html_content,
        "headers": {
            "Content-Type": "text/html"
        },
        "cookies": [
            f"visits={visits}; Expires={expires}; Path=/",
            f"last_visit={quote(current_time_str)}; Expires={expires}; Path=/"
        ]
    }
