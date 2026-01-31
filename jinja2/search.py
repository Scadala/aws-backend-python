import os
import logging
from datetime import datetime, date
from urllib.parse import unquote_plus
from dataclasses import dataclass, field
from functools import lru_cache

import boto3
import urllib3
from jinja2 import Environment, FileSystemLoader
import simplejson as json

# Set up logging
logger = logging.getLogger(__name__)

dynamodb = boto3.resource("dynamodb")
pmid_table = dynamodb.Table(os.environ["PMID_TABLE_NAME"])


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

    data = crossref_query(query=params.get("query"), rows=20)
    logger.info("data", extra={"data": data})

    pubmed_data = pubmed_query(query=params.get("query"), retmax=20)
    logger.info("pubmed_data", extra={"pubmed_data": pubmed_data})

    pmids = pubmed_data.get("esearchresult", {}).get("idlist", [])
    logger.info("pmids", extra={"pmids": pmids})

    dy_pmids = get_dy_pmids(pmids=pmids)
    logger.info("dy_pmids", extra={"dy_pmids": dy_pmids})

    pmids_in = {r["uid"] for r in dy_pmids}
    pmids_not_in = set(pmids) - pmids_in
    logger.info("pmids_not_in", extra={"pmids_not_in": list(pmids_not_in)})

    if len(pmids_not_in) == 0:
        logger.info("all pmids are in dynamodb")
    else:
        pubmed_summary_response = http.request(
            method="GET",
            url="https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=pubmed&retmode=json&id="
            + ",".join(pmids_not_in),
        )
        pubmed_summary_data = json.loads(pubmed_summary_response.data.decode("utf-8"))
        logger.info(
            "pubmed_summary_data", extra={"pubmed_summary_data": pubmed_summary_data}
        )

        with pmid_table.batch_writer() as batch:
            for uid, item in pubmed_summary_data.get("result", {}).items():
                if uid == "uids":
                    continue
                batch.put_item(Item=item)
        dy_pmids += get_dy_pmids(pmids=pmids_not_in)
        logger.info("dy_pmids", extra={"dy_pmids": dy_pmids})
    for item in dy_pmids:
        if "articleids" in item:
            for aid in item["articleids"]:
                if aid["idtype"] == "doi":
                    aid["value"]
    pmid_dois = {
        aid["value"]
        for item in dy_pmids
        for aid in item["articleids"]
        if aid["idtype"] == "doi"
    }
    logger.info("pmid_dois", extra={"pmid_dois": list(pmid_dois)})

    crossref_dois = {item["DOI"] for item in data["message"]["items"]}
    logger.info("crossref_dois", extra={"crossref_dois": list(crossref_dois)})

    logger.info(
        "dois intersection for " + params.get("query"),
        extra={"dois intersection": list(pmid_dois.intersection(crossref_dois))},
    )

    logger.info(
        "pmid dois ints",
        extra={
            "pmid dois ints": list(
                {int(d.split("/")[0].split(".")[-1]) for d in pmid_dois}
            )
        },
    )
    logger.info(
        "crossref dois ints",
        extra={
            "pmid dois ints": list(
                {
                    int(item["DOI"].split("/")[0].split(".")[-1])
                    for item in data["message"]["items"]
                }
            )
        },
    )

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


@lru_cache(maxsize=128)
def crossref_query(query: str, rows: int):
    response = http.request(
        method="GET",
        url=f"https://api.crossref.org/works?rows={rows}&query=" + query,
    )
    return json.loads(response.data.decode("utf-8"))


@lru_cache(maxsize=128)
def pubmed_query(query: str, retmax: int):
    pubmed_response = http.request(
        method="GET",
        url=f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&retmode=json&retmax={retmax}&sort=relevance&term="
        + query,
    )
    return json.loads(pubmed_response.data.decode("utf-8"))


def get_dy_pmids(pmids: list[str]):
    dyndb_response = dynamodb.batch_get_item(
        RequestItems={
            os.environ["PMID_TABLE_NAME"]: {"Keys": [{"uid": pmid} for pmid in pmids]}
        }
    )
    dy_list = dyndb_response.get("Responses", {}).get(os.environ["PMID_TABLE_NAME"], [])
    return json.loads(json.dumps(dy_list, use_decimal=True))
