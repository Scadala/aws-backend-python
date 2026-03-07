import os
import logging
from urllib.parse import unquote_plus

from jinja2 import Environment, FileSystemLoader

from .utils.crossref import cr_query
from .utils.pubmed import pubmed_query, search_dois
from .utils.nasa_ads import ads_query, search_ads_dois
from .utils import order_pubs

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

    params = event.get("queryStringParameters", {}) or {}
    logger.info("params", extra={"params": params})

    if "query" not in params:
        return {"statusCode": 302, "headers": {"Location": "/"}}
    query = params["query"]

    data = cr_query(query=query, rows=1000)  # 179300401
    pubmed_data = pubmed_query(query=query, retmax=224)  # 40143958
    nasa_ads_data = ads_query(query=query, rows=180)  # 32296235

    doi2pmid = {
        doi: pmid
        for pm_data in pubmed_data
        for doi in pm_data.dois or []
        for pmid in pm_data.pmids or []
    }
    doi_no_pmid = {doi for d in data for doi in d.dois or [] if doi not in doi2pmid} | {
        doi for d in nasa_ads_data for doi in d.dois or [] if doi not in doi2pmid
    }
    logger.info("doi_no_pmid", extra={"len": len(doi_no_pmid)})
    assert "None" not in doi2pmid.values(), len(
        [doi for doi, pmid in doi2pmid.items() if pmid == "None"]
    )
    doi2pmid |= search_dois(list(doi_no_pmid))
    assert "None" not in doi2pmid.values(), len(
        [doi for doi, pmid in doi2pmid.items() if pmid == "None"]
    )
    for d in data:
        d.pmids += [
            doi2pmid[doi]
            for doi in d.dois
            if doi in doi2pmid and doi2pmid[doi] not in d.pmids
        ]
    for d in nasa_ads_data:
        d.pmids += [
            doi2pmid[doi]
            for doi in d.dois
            if doi in doi2pmid and doi2pmid[doi] not in d.pmids
        ]
    doi2ads = {
        doi: ads_data for ads_data in nasa_ads_data for doi in ads_data.dois or []
    }
    doi_no_ads = {doi for d in data for doi in d.dois or [] if doi not in doi2ads}
    logger.info("doi_no_ads", extra={"len": len(doi_no_ads)})
    doi2ads |= search_ads_dois(list(doi_no_ads))
    for d in data:
        d.bibcodes += [
            doi2ads[doi]
            for doi in d.dois
            if doi in doi2ads and doi2ads[doi] not in d.bibcodes
        ]
    for d in pubmed_data:
        d.bibcodes += [
            doi2ads[doi]
            for doi in d.dois
            if doi in doi2ads and doi2ads[doi] not in d.bibcodes
        ]

    return {
        "statusCode": 200,
        "isBase64Encoded": False,
        "body": index_template.render(
            isindex=True,
            name=session.get("name"),
            title=params.get("query"),
            pubs=order_pubs(data, pubmed_data, nasa_ads_data),
        ),
        "headers": {"Content-Type": "text/html"},
        "cookies": [f"{k}={v}" for k, v in session.items()],
    }
