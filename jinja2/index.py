import os
import logging
from jinja2 import Environment, FileSystemLoader
from datetime import datetime

# Set up logging
logger = logging.getLogger(__name__)

# Set up Jinja2 environment to load templates from the templates directory
template_dir = os.path.join(os.path.dirname(__file__), 'templates')
jinja_env = Environment(loader=FileSystemLoader(template_dir))

# Load the template once at module initialization for better performance
template = jinja_env.get_template('index.html')

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
    logger.info("execution started", extra={"event": event})
    cookies = {cookie.split('=')[0]: cookie.split('=')[1] for cookie in event.get('cookies', []) if '=' in cookie}
    logger.info("cookies", extra={"cookies": cookies})
        
    # Render the template with visit information
    html_content = template.render(
        message="Hello World",
        visits=cookies.get("visits", 0),
        last_visit=cookies.get("last_visit", "never")
    )
    
    cookies["visits"] = int(cookies.get("visits", 0)) + 1
    cookies["last_visit"] = datetime.utcnow().isoformat()
    return {
        "statusCode": 200,
        "isBase64Encoded": False,
        "body": html_content,
        "headers": {
            "Content-Type": "text/html"
        },
        "cookies" : [f"{k}={v}" for k,v in cookies.items()],
    }
