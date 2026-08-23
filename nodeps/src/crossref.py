import json
import logging
import os

import urllib3

logger = logging.getLogger(__name__)

os.environ["DOI_CITS_TABLE_NAME"]
http = urllib3.PoolManager(headers={"User-Agent": "georgwendorf@gmail.com"})


def lambda_handler(event, context):
    logger.info("recieved event", extra={"event": event})

    response = http.request(
        method="GET",
        url=(
            "https://api.crossref.org/works?sort=indexed&order=desc&select=reference,DOI,indexed&rows=1000&cursor="
            + event.get("cursor", "*")
        ),
    )
    data = json.loads(response.data.decode("utf-8"))
    logger.info("cr_crawl", extra={"data": data})
