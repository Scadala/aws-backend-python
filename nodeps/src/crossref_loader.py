import logging
import os

import boto3

logger = logging.getLogger(__name__)


table = boto3.resource("dynamodb").Table(os.environ["DOI_CITS_TABLE_NAME"])


def lambda_handler(event, context):
    logger.info("recieved event", extra={"event": event})

    doi = event["doi"]
    ref = event["ref"]
    table_content = table.get_item(Key={"doi": ref})

    entry = table_content.get("Item")
    if entry is None:
        table.put_item(Item={"doi": ref, "cits": [doi]})
    elif doi not in entry["cits"]:
        entry["cits"].append(doi)
        table.put_item(Item=entry)
