import os
import logging
from jinja2 import Environment, FileSystemLoader
from datetime import datetime, date
from urllib.parse import unquote_plus
import urllib3
import json
from dataclasses import dataclass, field

# Set up logging
logger = logging.getLogger(__name__)

# Set up Jinja2 environment to load templates from the templates directory
template_dir = os.path.join(os.path.dirname(__file__), "templates")
jinja_env = Environment(loader=FileSystemLoader(template_dir))

# Load the template once at module initialization for better performance
index_template = jinja_env.get_template("query.html")

http = urllib3.PoolManager(headers={"User-Agent": "georgwendorf@gmail.com"})


@dataclass
class Publication:
    title: str
    ncits: int = 0
    pmids: list[int] | None = field(default_factory=list)
    dois: list[str] | None = field(default_factory=list)
    pdate: date | None = None
    bibcodes: list[str] = field(default_factory=list)


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

    response = http.request(
        method="GET",
        url="https://api.crossref.org/works?query=" + params.get("query"),
    )
    data = json.loads(response.data.decode("utf-8"))
    logger.info("data", extra={"data": data})

    return {
        "statusCode": 200,
        "isBase64Encoded": False,
        "body": index_template.render(
            isindex=True,
            name=session.get("name"),
            title=params.get("query"),
            pubs=[
                Publication(
                    title=item.get("title", [None])[0],
                    dois=[item["DOI"]],
                    pdate=pdate_from_item(item),
                )
                for item in data["message"]["items"]
            ],
        ),
        "headers": {"Content-Type": "text/html"},
        "cookies": [f"{k}={v}" for k, v in session.items()],
    }


def pdate_from_item(item):
    for pdatetag in [
        "issued",
        "posted",
        "accepted",
        "published-print",
        "published-online",
    ]:
        if pdatetag in item and None not in item[pdatetag]["date-parts"][0][:3]:
            return date(*(item[pdatetag]["date-parts"][0] + [1, 1])[:3])
