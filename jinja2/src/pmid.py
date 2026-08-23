import logging
import os
from urllib.parse import unquote_plus

from jinja2 import Environment, FileSystemLoader

from .utils import Pub
from .utils.pubmed import batch_id_to_known_pub

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

    pmid = event["pathParameters"]["pmid"]

    data = batch_id_to_known_pub(pmids=[pmid])[pmid]

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
            refs=[Pub(pmids=ref.pmids) for ref in data.refs] if data.refs else [],
        ),
        "headers": {"Content-Type": "text/html"},
        "cookies": [f"{k}={v}" for k, v in session.items()],
    }
