import os
import logging
from jinja2 import Environment, FileSystemLoader
from urllib.parse import unquote_plus

from .utils.nasa_ads import ads_query


# Set up logging
logger = logging.getLogger(__name__)

# Set up Jinja2 environment to load templates from the templates directory
template_dir = os.path.join("templates")
jinja_env = Environment(loader=FileSystemLoader(template_dir))

# Load the template once at module initialization for better performance
index_template = jinja_env.get_template("publication.html")


def lambda_handler(event, context):
    """Sample Lambda function which returns an HTML response rendered by Jinja2"""
    logger.info("execution started", extra={"event": event})
    session = {
        cookie.split("=")[0]: unquote_plus(cookie.split("=")[1])
        for cookie in event.get("cookies", [])
        if "=" in cookie
    }
    logger.info("session", extra={"session": session})

    bibcode = event["pathParameters"]["bibcode"]

    data = ads_query(query=f"alternate_bibcode:{bibcode} or bibcode:{bibcode}")[0]

    return {
        "statusCode": 200,
        "isBase64Encoded": False,
        "body": index_template.render(
            isindex=False,
            name=session.get("name"),
            title=data.title if data.title else "",
            rawPath=event["rawPath"],
            orcweb=None,
            pub=data,
            refs=[],
        ),
        "headers": {"Content-Type": "text/html"},
        "cookies": [f"{k}={v}" for k, v in session.items()],
    }
