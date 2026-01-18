import os
import logging
from jinja2 import Environment, FileSystemLoader
from datetime import date
from urllib.parse import unquote_plus
import urllib3
import json
from dataclasses import dataclass

# Set up logging
logger = logging.getLogger(__name__)

# Set up Jinja2 environment to load templates from the templates directory
template_dir = os.path.join(os.path.dirname(__file__), "templates")
jinja_env = Environment(loader=FileSystemLoader(template_dir))

# Load the template once at module initialization for better performance
index_template = jinja_env.get_template("publication.html")

http = urllib3.PoolManager(headers={"User-Agent": "georgwendorf@gmail.com"})


def lambda_handler(event, context):
    """Sample Lambda function which returns an HTML response rendered by Jinja2"""
    logger.info("execution started", extra={"event": event})
    session = {
        cookie.split("=")[0]: unquote_plus(cookie.split("=")[1])
        for cookie in event.get("cookies", [])
        if "=" in cookie
    }
    logger.info("session", extra={"session": session})

    response = http.request(
        method="GET",
        url="https://api.crossref.org/works/" + event["pathParameters"]["doi"],
    )
    data = json.loads(response.data.decode("utf-8"))
    logger.info("data", extra={"data": data})
    return {
        "statusCode": 200,
        "isBase64Encoded": False,
        "body": index_template.render(
            isindex=True,
            name=session.get("name"),
            title=data["message"]["title"][0],
            rawPath=event["rawPath"],
            orcweb=None,
            pub=make_pub(data["message"]),
            refs=[
                make_ref(r) for r in data["message"].get("reference", []) if "DOI" in r
            ],
        ),
        "headers": {"Content-Type": "text/html"},
        "cookies": [f"{k}={v}" for k, v in session.items()],
    }


def make_pub(data):
    _pdate = pdate_from_item(data)
    return Pub(
        pdate=_pdate.isoformat() if _pdate is not None else "",
        abstract=data.get("abstract"),
        title=data.get("title", [None])[0],
        orcs=[make_orc(o) for o in data.get("author", []) if "ORCID" in o],
        doi=data.get("DOI"),
    )


def make_orc(data):
    return Orc(
        shortshort=data.get("ORCID").split("/")[-1],
        name=data.get("family"),
    )


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


@dataclass
class Orc:
    shortshort: str
    name: str


@dataclass
class Pub:
    pdate: str
    abstract: str | None
    title: str | None
    orcs: list[Orc]
    doi: str


@dataclass
class DoiRef:
    doi: str
    pdate: str
    title: str


def make_ref(data):
    return DoiRef(
        doi=data["DOI"],
        title=data.get("unstructured"),
        pdate=data.get("year"),
    )
