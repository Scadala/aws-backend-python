import simplejson as json
import logging
import os

import boto3
import urllib3
from dataclasses import dataclass, asdict


from xml.etree import ElementTree

logger = logging.getLogger(__name__)
dynamodb = boto3.resource("dynamodb")


http = urllib3.PoolManager(headers={"User-Agent": "georgwendorf@gmail.com"})


ssm_client = boto3.client("ssm", region_name="eu-central-1")

nasa_ads_token = ssm_client.get_parameter(
    Name="arn:aws:ssm:eu-central-1:796401245269:parameter"
    + "/api-token/api.adsabs.harvard.edu/georgwendorf_gmail.com",
    WithDecryption=True,
)["Parameter"]["Value"]


@dataclass
class Orc:
    shortshort: str
    name: str


@dataclass
class Pub:
    pdate: str | None = None
    abstract: str | None = None
    title: str | None = None
    orcs: list[Orc] | None = None
    dois: list[str] | None = None
    pmcids: list[str] | None = None
    pmids: list[str] | None = None
    bibcodes: list[str] | None = None
    refs: list["Pub"] | None = None
    cits: list["Pub"] | None = None


def get_dy_pmids(pmids: list[str]) -> dict[str, Pub]:
    dyndb_response = dynamodb.batch_get_item(
        RequestItems={
            os.environ["PMID_TABLE_NAME"]: {"Keys": [{"pmid": pmid} for pmid in pmids]}
        }
    )
    dy_list = dyndb_response.get("Responses", {}).get(os.environ["PMID_TABLE_NAME"], [])
    # return {d["uid"]: d for d in json.loads(json.dumps(dy_list, use_decimal=True))}

    dy_pmids = {
        d["pmid"]: Pub(**d) for d in json.loads(json.dumps(dy_list, use_decimal=True))
    }
    logger.info("dy_pmids", extra={"dy_pmids": dy_pmids})

    pmids_not_in = set(pmids) - dy_pmids.keys()
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
            pmid = pmid_element.text

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

            pmc_element = pubmed_article.find(
                ".//PubmedData/ArticleIdList/ArticleId[@IdType='pmc']"
            )
            pmc = pmc_element.text if pmc_element is not None else None

            refs_elements = pubmed_article.findall(
                ".//PubmedData/ReferenceList/Reference/ArticleIdList/ArticleId[@IdType='pubmed']"
            )

            dy_pmids[pmid] = Pub(
                pmids=[pmid],
                title=title,
                abstract=abstract,
                pdate=sortpubdate,
                dois=[doi] if doi else None,
                pmcids=[pmc] if pmc else None,
                refs=[
                    Pub(pmids=[ref_element.text])
                    for ref_element in refs_elements
                    if ref_element.text is not None
                ],
            )
        logger.info(
            "dy_pmids",
            extra={
                "dy_pmids": {
                    pmid: asdict(pmid_data) for pmid, pmid_data in dy_pmids.items()
                }
            },
        )
    return dy_pmids


def ads_query(query: str, rows: int, detailed: bool = False) -> list[Pub]:
    fl = [
        "title",
        "bibcode",
        "doi",
        "pubdate",
        "alternate_bibcode",
        "identifier",
        "id",
    ]
    if detailed:
        fl += ["abstract", "author", "aff", "orcid"]
    response = http.request(
        method="GET",
        url=f"https://api.adsabs.harvard.edu/v1/search/query?fl={','.join(fl)}&q={query}&rows={rows}",
        headers={"Authorization": f"Bearer {nasa_ads_token}"},
    )
    jresp = json.loads(response.data.decode("utf-8"))
    logger.info("ads_query_response", extra={"ads_query_response": jresp})
    return [
        Pub(
            title=p.get("title", [None])[0],
            pdate=p.get("pubdate"),
            bibcodes=[p.get("bibcode")] + p.get("alternate_bibcode", []),
            abstract=p.get("abstract"),
            dois=p.get("doi"),
        )
        for p in jresp.get("response", {}).get("docs", [])
    ]
