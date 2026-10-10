import logging
import os

import boto3
from botocore.config import Config

logger = logging.getLogger(__name__)


table = boto3.resource(
    "dynamodb", config=Config(connect_timeout=1, read_timeout=1)
).Table(os.environ["DOI_CITS_TABLE_NAME"])


def lambda_handler(event, context):
    logger.info("recieved event", extra={"event": event})

    doi = event["doi"]
    for ref in event["refs"]:
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
