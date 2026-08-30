import logging
import os

import boto3

logger = logging.getLogger(__name__)


table = boto3.resource("dynamodb").Table(os.environ["DOI_CITS_TABLE_NAME"])


def lambda_handler(event, context):
    logger.info("recieved event", extra={"event": event})

    for record in event["Records"]:
        attributes = record["messageAttributes"]
        doi = attributes["doi"]["stringValue"]
        ref = attributes["ref"]["stringValue"]
        table_content = table.get_item(Key={"doi": ref})

        entry = table_content.get("Item")
        if entry is None:
            result = table.put_item(Item={"doi": ref, "cits": [doi]})
            logger.info("put_item", extra={"result": result, "doi": doi, "ref": ref})
        elif doi not in entry["cits"]:
            entry["cits"].append(doi)
            result = table.put_item(Item=entry)
            logger.info("update_item", extra={"result": result, "doi": doi, "ref": ref})
        else:
            logger.info(
                "already exists",
                extra={"doi": doi, "ref": ref, "cits": entry["cits"]},
            )
