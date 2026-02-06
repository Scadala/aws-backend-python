import simplejson as json
import logging
import os

import boto3
import urllib3

logger = logging.getLogger(__name__)
dynamodb = boto3.resource("dynamodb")


http = urllib3.PoolManager(headers={"User-Agent": "georgwendorf@gmail.com"})


def get_dy_pmids(pmids: set[str]):
    dyndb_response = dynamodb.batch_get_item(
        RequestItems={
            os.environ["PMID_TABLE_NAME"]: {"Keys": [{"uid": pmid} for pmid in pmids]}
        }
    )
    dy_list = dyndb_response.get("Responses", {}).get(os.environ["PMID_TABLE_NAME"], [])
    # return {d["uid"]: d for d in json.loads(json.dumps(dy_list, use_decimal=True))}

    dy_pmids = {d["uid"]: d for d in json.loads(json.dumps(dy_list, use_decimal=True))}
    logger.info("dy_pmids", extra={"dy_pmids": dy_pmids})

    pmids_not_in = pmids - dy_pmids.keys()
    logger.info("pmids_not_in", extra={"pmids_not_in": list(pmids_not_in)})

    if len(pmids_not_in) > 0:
        pubmed_summary_response = http.request(
            method="GET",
            url="https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=pubmed&retmode=json&id="
            + ",".join(pmids_not_in),
        )
        pubmed_summary_data = json.loads(pubmed_summary_response.data.decode("utf-8"))
        logger.info(
            "pubmed_summary_data", extra={"pubmed_summary_data": pubmed_summary_data}
        )

        with dynamodb.Table(os.environ["PMID_TABLE_NAME"]).batch_writer() as batch:
            for uid, item in pubmed_summary_data.get("result", {}).items():
                if uid == "uids":
                    continue
                batch.put_item(Item=item)
        dy_pmids |= get_dy_pmids(pmids=pmids_not_in)
        logger.info("dy_pmids", extra={"dy_pmids": dy_pmids})
    return dy_pmids
