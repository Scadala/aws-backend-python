import logging
import os

import boto3
import urllib3

logger = logging.getLogger(__name__)

os.environ["DOI_CITS_TABLE_NAME"]
http = urllib3.PoolManager(headers={"User-Agent": "georgwendorf@gmail.com"})

ssm_client = boto3.client("ssm", region_name="eu-central-1")
dynamodb = boto3.resource("dynamodb")

CROSSREF_LAST_CRAWL_PARAM = ssm_client.get_parameter(
    Name=os.environ["CROSSREF_LAST_CRAWL_PARAM"],
)["Parameter"]["Value"]


def lambda_handler(event, context):
    logger.info(
        "recieved event",
        extra={"event": event, "CROSSREF_LAST_CRAWL_PARAM": CROSSREF_LAST_CRAWL_PARAM},
    )

    data = http.request(
        method="GET",
        url=(
            "https://api.crossref.org/works?sort=indexed&order=desc&select=reference,DOI,indexed&rows=1000&cursor="
            + event.get("cursor", "*")
        ),
    ).json()
    items = data["message"].pop("items")
    logger.info("cr_crawl", extra={"data": data})
    for i, item in enumerate(items):
        logger.info("item", extra={"i": i, "item": item})
        handle_item(item)


def handle_item(item):
    doi = item["DOI"].lower()
    indexed = item["indexed"]["date-time"]
    refs = list(
        {ref["DOI"].lower() for ref in item.get("reference", []) if "DOI" in ref}
    )
    logger.info("item prepared", extra={"doi": doi, "indexed": indexed, "refs": refs})
    for i in range(0, len(refs), 100):
        handle_batch_refs(doi, set(refs[i : i + 100]))


def handle_batch_refs(doi, refs):
    dyndb_entries = (
        dynamodb.batch_get_item(
            RequestItems={
                os.environ["DOI_CITS_TABLE_NAME"]: {
                    "Keys": [{"doi": ref} for ref in refs]
                }
            }
        )
        .get("Responses", {})
        .get(os.environ["DOI_CITS_TABLE_NAME"], [])
    )
    batch_size = 0
    with dynamodb.Table(os.environ["DOI_CITS_TABLE_NAME"]).batch_writer() as batch:
        for entry in dyndb_entries:
            refs -= {entry["doi"]}
            if doi not in entry["cits"]:
                entry["cits"].append(doi)
                batch.put_item(Item=entry)
                batch_size += 1
        for ref in refs:
            batch.put_item(Item={"doi": ref, "cits": [doi]})
            batch_size += 1
    logger.info("batch written", extra={"batch_size": batch_size})
