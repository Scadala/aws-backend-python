import os
from jinja2 import Environment, FileSystemLoader, TemplateNotFound

# Set up Jinja2 environment to load templates from the templates directory
template_dir = os.path.join(os.path.dirname(__file__), 'templates')
jinja_env = Environment(loader=FileSystemLoader(template_dir))

# Load the template once at module initialization for better performance
try:
    template = jinja_env.get_template('index.html')
except TemplateNotFound:
    template = None

def lambda_handler(event, context):
    """Sample Lambda function which returns an HTML response rendered by Jinja2

    Parameters
    ----------
    event: dict, required
        API Gateway Lambda Proxy Input Format

        Event doc: https://docs.aws.amazon.com/apigateway/latest/developerguide/set-up-lambda-proxy-integrations.html#api-gateway-simple-proxy-for-lambda-input-format

    context: object, required
        Lambda Context runtime methods and attributes

        Context doc: https://docs.aws.amazon.com/lambda/latest/dg/python-context-object.html

    Returns
    ------
    API Gateway Lambda Proxy Output Format: dict

        Return doc: https://docs.aws.amazon.com/apigateway/latest/developerguide/set-up-lambda-proxy-integrations.html
    """

    # Check if template was loaded successfully
    if template is None:
        return {
            "statusCode": 500,
            "body": "<h1>Internal Server Error: Template not found</h1>",
            "headers": {
                "Content-Type": "text/html"
            }
        }

    # Render the template
    html_content = template.render(message="Hello World")

    return {
        "statusCode": 200,
        "body": html_content,
        "headers": {
            "Content-Type": "text/html"
        }
    }
