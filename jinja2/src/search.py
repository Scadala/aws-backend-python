import asyncio
import logging
import os
from urllib.parse import unquote_plus

import aiohttp
import boto3

from jinja2 import Environment, FileSystemLoader

from .utils import crossref, nasa_ads, order_pubs, pubmed
from .utils.nasa_ads import search_ads_dois
from .utils.pubmed import search_dois

# Set up logging
logger = logging.getLogger(__name__)


# Set up Jinja2 environment to load templates from the templates directory
template_dir = os.path.join("templates")
jinja_env = Environment(loader=FileSystemLoader(template_dir))

# Load the template once at module initialization for better performance
index_template = jinja_env.get_template("query.html")


sqs_client = boto3.client("sqs", region_name="eu-central-1")
ssm_client = boto3.client("ssm", region_name="eu-central-1")
nasa_ads_token = ssm_client.get_parameter(
    Name="arn:aws:ssm:eu-central-1:796401245269:parameter"
    + "/api-token/api.adsabs.harvard.edu/georgwendorf_gmail.com",
    WithDecryption=True,
)["Parameter"]["Value"]


async def fetch(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(**url) as resp:
            return await resp.json()


async def fetch_all(urls):
    tasks = [fetch(url) for url in urls]
    return await asyncio.gather(*tasks)


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
    urls = [
        {
            "url": "https://api.crossref.org/works?rows=1000&query="
            + query,  # 179300401
            "headers": {"User-Agent": "georgwendorf@gmail.com"},
        },
        {
            "url": f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&retmode=json&retmax=224&sort=relevance&term={query}",  # 40143958
            "headers": {"User-Agent": "georgwendorf@gmail.com"},
        },
        {
            "url": f"https://api.adsabs.harvard.edu/v1/search/query?fl=title,bibcode,doi,pubdate,alternate_bibcode&q={query}&rows=180",  # 32296235
            "headers": {
                "User-Agent": "georgwendorf@gmail.com",
                "Authorization": f"Bearer {nasa_ads_token}",
            },
        },
    ]
    responses = asyncio.run(fetch_all(urls=urls))
    logger.info(
        "response lengths",
        extra={
            "api.crossref.org": len(responses[0]["message"]["items"]),
            "eutils.ncbi.nlm.nih.gov": len(responses[1]["esearchresult"]["idlist"]),
            "api.adsabs.harvard.edu": len(responses[2]["response"]["docs"]),
        },
    )

    data = [
        crossref.item_to_pub(item=item) for item in responses[0]["message"]["items"]
    ]
    known_pubmed = pubmed.batch_id_to_known_pub(
        pmids=responses[1]["esearchresult"]["idlist"]
    )
    for pmid in responses[1]["esearchresult"]["idlist"]:
        if pmid not in known_pubmed:
            sqs_client.send_message(
                QueueUrl=os.environ["PMID_LOOKUP_QUEUE"],
                MessageBody=pmid,
            )
    pubmed_data = list(known_pubmed.values())
    nasa_ads_data = [
        nasa_ads.doc_to_pub(doc) for doc in responses[2]["response"]["docs"]
    ]

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
        doi: bibcode
        for ads_data in nasa_ads_data
        for doi in ads_data.dois
        for bibcode in ads_data.bibcodes
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
