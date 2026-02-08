import os
import logging
from urllib.parse import unquote_plus
from collections import defaultdict

from jinja2 import Environment, FileSystemLoader

from .utils.crossref import cr_query
from .utils.pubmed import pubmed_query
from .utils.nasa_ads import ads_query

# Set up logging
logger = logging.getLogger(__name__)


# Set up Jinja2 environment to load templates from the templates directory
template_dir = os.path.join("templates")
jinja_env = Environment(loader=FileSystemLoader(template_dir))

# Load the template once at module initialization for better performance
index_template = jinja_env.get_template("query.html")


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
    session = {
        cookie.split("=")[0]: unquote_plus(cookie.split("=")[1])
        for cookie in event.get("cookies", [])
        if "=" in cookie
    }
    logger.info("session", extra={"session": session})

    params = {
        k: v
        for k, v in (
            item.split("=")
            for item in event.get("rawQueryString", "query=").split("&")
            if "=" in item
        )
    }
    logger.info("params", extra={"params": params})

    if "query" not in params:
        return {"statusCode": 302, "headers": {"Location": "/"}}
    query = params["query"]

    logger.info("before nasa ads data")
    nasa_ads_data = ads_query(query=query, rows=25)
    logger.info("after nasa ads data, len: %s", len(nasa_ads_data))

    data = cr_query(query=query, rows=25)

    dois = {doi for pub in data for doi in pub.dois}
    q_pubmed = query
    if len(dois) > 0:
        q_pubmed += "+OR+"
        q_pubmed += "+OR+".join([f"{d}[aid]" for d in dois])

    pubmed_data = pubmed_query(query=q_pubmed, retmax=25)

    doi2pmids = defaultdict(set)
    for dy_pmid in pubmed_data:
        if dy_pmid.dois:
            for doi in dy_pmid.dois:
                doi2pmids[doi].add(dy_pmid.pmids[0])

    return {
        "statusCode": 200,
        "isBase64Encoded": False,
        "body": index_template.render(
            isindex=True,
            name=session.get("name"),
            title=params.get("query"),
            pubs=data + pubmed_data + nasa_ads_data,
        ),
        "headers": {"Content-Type": "text/html"},
        "cookies": [f"{k}={v}" for k, v in session.items()],
    }
