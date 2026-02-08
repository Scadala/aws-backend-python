from . import Pub

import logging
import simplejson as json
from datetime import date
import urllib3

http = urllib3.PoolManager(headers={"User-Agent": "georgwendorf@gmail.com"})

logger = logging.getLogger(__name__)


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
        dois=[data["message"]["DOI"]],
    )


def cr_query(query: str, rows: int) -> list[Pub]:
    response = http.request(
        method="GET",
        url=f"https://api.crossref.org/works?rows={rows}&query=" + query,
    )
    data = json.loads(response.data.decode("utf-8"))

    logger.info("cr_query", extra={"data": data})
    return [
        Pub(
            pdate=pdate_from_item(item),
            abstract=item.get("abstract"),
            title=item.get("title", [None])[0],
            orcs=[],
            dois=[item["DOI"]],
        )
        for item in data["message"]["items"]
    ]
