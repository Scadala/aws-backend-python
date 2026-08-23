import logging
import os

import simplejson as json
import urllib3

logger = logging.getLogger(__name__)

os.environ["DOI_CITS_TABLE_NAME"]
http = urllib3.PoolManager(headers={"User-Agent": "georgwendorf@gmail.com"})


def lambda_handler(event, context):
    logger.info("recieved event", extra={"event": event})

    data = http.request(
        method="GET",
        url=(
            "https://api.crossref.org/works?sort=indexed&order=desc&select=reference,DOI,indexed&rows=1000&cursor="
            + event.get("cursor", "*")
        ),
    ).json()
    items = data["message"].pop("items")
    logger.info("cr_crawl", extra={"data": data})
    for item in items:
        handle_item(item)


def handle_item(item):
    doi = item["DOI"].lower()
    indexed = item["indexed"]["date-time"]
    for ref in {
        ref["DOI"].lower() for ref in item.get("reference", []) if "DOI" in ref
    }:
        handle_ref(doi, ref)


def handle_ref(doi, ref):
    pass
