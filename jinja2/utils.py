import simplejson as json
import logging
import os

import boto3
import urllib3
from dataclasses import dataclass


from xml.etree import ElementTree

logger = logging.getLogger(__name__)
dynamodb = boto3.resource("dynamodb")


http = urllib3.PoolManager(headers={"User-Agent": "georgwendorf@gmail.com"})


@dataclass
class Pmid:
    pmid: int
    title: str
    abstract: str
    sortpubdate: str


def get_dy_pmids(pmids: set[str]):
    dyndb_response = dynamodb.batch_get_item(
        RequestItems={
            os.environ["PMID_TABLE_NAME"]: {
                "Keys": [{"pmid": int(pmid)} for pmid in pmids]
            }
        }
    )
    dy_list = dyndb_response.get("Responses", {}).get(os.environ["PMID_TABLE_NAME"], [])
    # return {d["uid"]: d for d in json.loads(json.dumps(dy_list, use_decimal=True))}

    dy_pmids = {d["pmid"]: d for d in json.loads(json.dumps(dy_list, use_decimal=True))}
    logger.info("dy_pmids", extra={"dy_pmids": dy_pmids})

    pmids_not_in = pmids - dy_pmids.keys()
    logger.info("pmids_not_in", extra={"pmids_not_in": list(pmids_not_in)})

    if len(pmids_not_in) > 0:
        pubmed_summary_response = http.request(
            method="GET",
            url="https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&retmode=xml&id="
            + ",".join(pmids_not_in),
        )
        pubmed_summary_data = ElementTree.fromstring(pubmed_summary_response.data)
        for pubmed_article in pubmed_summary_data.findall(".//PubmedArticle"):
            pmid = pubmed_article.find(".//MedlineCitation/PMID").text
            title = pubmed_article.find(".//MedlineCitation/Article/ArticleTitle").text
            abstract = pubmed_article.find(
                ".//MedlineCitation/Article/Abstract/AbstractText"
            )
            abstract = abstract.text if abstract is not None else ""
            sortpubdate = pubmed_article.find(
                ".//MedlineCitation/Article/ArticleDate[@DateType='Electronic']"
            )
            if sortpubdate is None:
                sortpubdate = pubmed_article.find(
                    ".//MedlineCitation/Article/ArticleDate[@DateType='Print']"
                )
            sortpubdate = (
                f"{sortpubdate.find('Year').text}-{sortpubdate.find('Month').text.zfill(2)}-{sortpubdate.find('Day').text.zfill(2)}"
                if sortpubdate is not None
                else ""
            )

            dy_pmids[pmid] = {
                "pmid": int(pmid),
                "title": title,
                "abstract": abstract,
                "sortpubdate": sortpubdate,
            }
        logger.info("dy_pmids", extra={"dy_pmids": dy_pmids})
    return dy_pmids


def get_abstract(pmid: str):
    dy_pmids = get_dy_pmids(pmids={pmid})
    return dy_pmids.get(pmid, {}).get("abstract", "")
