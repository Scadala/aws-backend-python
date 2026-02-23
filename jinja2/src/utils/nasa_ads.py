import os
import sys
import boto3

from . import Pub
import simplejson as json
import logging
import urllib3

http = urllib3.PoolManager(headers={"User-Agent": "georgwendorf@gmail.com"})


logger = logging.getLogger(__name__)

ssm_client = boto3.client("ssm", region_name="eu-central-1")

dynamodb = boto3.resource("dynamodb")
nasa_ads_token = ssm_client.get_parameter(
    Name="arn:aws:ssm:eu-central-1:796401245269:parameter"
    + "/api-token/api.adsabs.harvard.edu/georgwendorf_gmail.com",
    WithDecryption=True,
)["Parameter"]["Value"]


def ads_query(query: str, rows: int = 10, detailed: bool = False) -> list[Pub]:
    fl = [
        "title",
        "bibcode",
        "doi",
        "pubdate",
        "alternate_bibcode",
    ]
    if detailed:
        fl += ["abstract", "author", "aff", "orcid"]
    url = f"https://api.adsabs.harvard.edu/v1/search/query?fl={','.join(fl)}&q={query}&rows={rows}"
    dyndb_response = dynamodb.Table(os.environ["SEARCH_CACHE_TABLE_NAME"]).get_item(
        Key={"url": url}
    )
    if "Item" in dyndb_response:
        logger.info("ads_query cache hit", extra={"url": url})
        decoded_response = str(dyndb_response["Item"]["response"])
    else:
        logger.info("ads_query cache miss", extra={"url": url})
        response = http.request(
            method="GET",
            url=url,
            headers={"Authorization": f"Bearer {nasa_ads_token}"},
        )
        decoded_response = response.data.decode("utf-8")
        _jresp = json.loads(decoded_response)
        _docs = _jresp.get("response", {}).pop("docs", [])
        logger.info("ads_query_response json", extra={"ads_query_response": _jresp})
        logger.info(
            "ads_query_response", extra={"size": sys.getsizeof(decoded_response)}
        )
        dynamodb.Table(os.environ["SEARCH_CACHE_TABLE_NAME"]).put_item(
            Item={
                "url": url,
                "response": decoded_response,
            }
        )
    jresp = json.loads(decoded_response)
    logger.info("ads_query_response", extra={"ads_query_response": jresp})
    return [
        Pub(
            title=p.get("title", [None])[0],
            pdate=p.get("pubdate"),
            bibcodes=[p.get("bibcode")] + p.get("alternate_bibcode", []),
            abstract=p.get("abstract"),
            dois=[doi.lower() for doi in p["doi"]] if p.get("doi") else None,
        )
        for p in jresp.get("response", {}).get("docs", [])
    ]
