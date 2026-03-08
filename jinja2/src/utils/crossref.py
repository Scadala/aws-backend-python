import logging
import os
from datetime import date

import boto3
import simplejson as json
import urllib3

from . import Pub

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


def item_to_pub(item) -> Pub:
    return Pub(
        pdate=pdate_from_item(item),
        title=item.get("title", [None])[0],
        orcs=[],
        dois=[item["DOI"].lower()],
    )
