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
    title: str | None
    abstract: str | None
    sortpubdate: str | None
    doi: str | None


def get_dy_pmids(pmids: set[int]) -> dict[int, Pmid]:
    dyndb_response = dynamodb.batch_get_item(
        RequestItems={
            os.environ["PMID_TABLE_NAME"]: {
                "Keys": [{"pmid": int(pmid)} for pmid in pmids]
            }
        }
    )
    dy_list = dyndb_response.get("Responses", {}).get(os.environ["PMID_TABLE_NAME"], [])
    # return {d["uid"]: d for d in json.loads(json.dumps(dy_list, use_decimal=True))}

    dy_pmids = {
        d["pmid"]: Pmid(**d) for d in json.loads(json.dumps(dy_list, use_decimal=True))
    }
    logger.info("dy_pmids", extra={"dy_pmids": dy_pmids})

    pmids_not_in = pmids - dy_pmids.keys()
    logger.info("pmids_not_in", extra={"pmids_not_in": list(pmids_not_in)})

    if len(pmids_not_in) > 0:
        pubmed_summary_response = http.request(
            method="GET",
            url="https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&retmode=xml&id="
            + ",".join([str(pmid) for pmid in pmids_not_in]),
        )
        pubmed_summary_data = ElementTree.fromstring(pubmed_summary_response.data)
        for pubmed_article in pubmed_summary_data.findall(".//PubmedArticle"):
            pmid_element = pubmed_article.find(".//MedlineCitation/PMID")
            assert pmid_element is not None
            assert pmid_element.text is not None
            pmid = int(pmid_element.text)

            title_element = pubmed_article.find(
                ".//MedlineCitation/Article/ArticleTitle"
            )
            title = title_element.text if title_element is not None else ""

            abstract_element = pubmed_article.find(
                ".//MedlineCitation/Article/Abstract/AbstractText"
            )
            abstract = abstract_element.text if abstract_element is not None else ""

            sortpubdate_element = pubmed_article.find(
                ".//MedlineCitation/Article/ArticleDate[@DateType='Electronic']"
            ) or pubmed_article.find(
                ".//MedlineCitation/Article/ArticleDate[@DateType='Print']"
            )
            if sortpubdate_element:
                year_element = sortpubdate_element.find("Year")
                month_element = sortpubdate_element.find("Month")
                day_element = sortpubdate_element.find("Day")
                if year_element and year_element.text is not None:
                    year = year_element.text
                    month = "01"
                    day = "01"
                    if month_element is not None and month_element.text is not None:
                        month = month_element.text  # .zfill(2)
                    if day_element is not None and day_element.text is not None:
                        day = day_element.text  # .zfill(2)
                    sortpubdate = f"{year}-{month}-{day}"
                else:
                    sortpubdate = None
            else:
                sortpubdate = None

            doi_element = pubmed_article.find(
                ".//PubmedData/ArticleIdList/ArticleId[@IdType='doi']"
            )
            doi = doi_element.text if doi_element is not None else None

            dy_pmids[pmid] = Pmid(
                pmid=pmid,
                title=title,
                abstract=abstract,
                sortpubdate=sortpubdate,
                doi=doi,
            )
        logger.info("dy_pmids", extra={"dy_pmids": dy_pmids})
    return dy_pmids
