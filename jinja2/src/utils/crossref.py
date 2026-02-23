import os
import boto3
from . import Pub

import logging
import simplejson as json
from datetime import date
import urllib3

http = urllib3.PoolManager(headers={"User-Agent": "georgwendorf@gmail.com"})

logger = logging.getLogger(__name__)

dynamodb = boto3.resource("dynamodb")

pdatetags = [
    "issued",
    "posted",
    "accepted",
    "published-print",
    "published-online",
]


def pdate_from_item(item):
    for pdatetag in pdatetags:
        if pdatetag in item and None not in item[pdatetag]["date-parts"][0][:3]:
            return date(*(item[pdatetag]["date-parts"][0] + [1, 1])[:3])


def cr_lookup(doi) -> Pub:
    logger.info("cr_lookup", extra={"doi": doi})
    response = http.request(
        method="GET",
        url="https://api.crossref.org/works/" + doi,
    )
    data = json.loads(response.data.decode("utf-8"))
    logger.info("cr_lookup", extra={"data": data})
    return Pub(
        pdate=pdate_from_item(data["message"]),
        abstract=data["message"].get("abstract"),
        title=data["message"].get("title", [None])[0],
        orcs=[],
        dois=[data["message"]["DOI"].lower()],
    )


def cr_query(query: str, rows: int) -> list[Pub]:
    url = f"https://api.crossref.org/works?rows={rows}&query=" + query
    logger.info("cr_query", extra={"url": url})
    dyndb_response = dynamodb.Table(os.environ["SEARCH_CACHE_TABLE_NAME"]).get_item(
        Key={"url": url}
    )
    if "Item" in dyndb_response:
        logger.info("cr_query cache hit", extra={"url": url})
        decoded_response = str(dyndb_response["Item"]["response"])
    else:
        logger.info("cr_query cache miss", extra={"url": url})
        response = http.request(
            method="GET",
            url=url,
        )
        decoded_response = response.data.decode("utf-8")
        items = json.loads(decoded_response)["message"]["items"]
        dynamodb.Table(os.environ["SEARCH_CACHE_TABLE_NAME"]).put_item(
            Item={
                "url": url,
                "response": json.dumps(
                    {
                        "message": {
                            "items": [
                                {
                                    k: v
                                    for k, v in item.items()
                                    if k in pdatetags + ["title", "DOI"]
                                }
                                for item in items
                            ]
                        }
                    }
                ),
            },
        )
    data = json.loads(decoded_response)
    return [
        Pub(
            pdate=pdate_from_item(item),
            title=item.get("title", [None])[0],
            orcs=[],
            dois=[item["DOI"].lower()],
        )
        for item in data["message"]["items"]
    ]
