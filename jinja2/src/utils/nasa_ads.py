import os
import sys
import boto3

from . import Pub
import simplejson as json
import logging
import urllib3

http = urllib3.PoolManager(headers={"User-Agent": "georgwendorf@gmail.com"})


logger = logging.getLogger(__name__)

ssm_client = boto3.client("ssm", region_name="eu-central-1")

dynamodb = boto3.resource("dynamodb")
nasa_ads_token = ssm_client.get_parameter(
    Name="arn:aws:ssm:eu-central-1:796401245269:parameter"
    + "/api-token/api.adsabs.harvard.edu/georgwendorf_gmail.com",
    WithDecryption=True,
)["Parameter"]["Value"]


def ads_query(query: str, rows: int = 10, detailed: bool = False) -> list[Pub]:
    fl = [
        "title",
        "bibcode",
        "doi",
        "pubdate",
        "alternate_bibcode",
    ]
    if detailed:
        fl += ["abstract", "author", "aff", "orcid"]
    url = f"https://api.adsabs.harvard.edu/v1/search/query?fl={','.join(fl)}&q={query}&rows={rows}"
    dyndb_response = dynamodb.Table(os.environ["SEARCH_CACHE_TABLE_NAME"]).get_item(
        Key={"url": url}
    )
    if "Item" in dyndb_response:
        logger.info("ads_query cache hit", extra={"url": url})
        decoded_response = str(dyndb_response["Item"]["response"])
    else:
        logger.info("ads_query cache miss", extra={"url": url})
        response = http.request(
            method="GET",
            url=url,
            headers={"Authorization": f"Bearer {nasa_ads_token}"},
        )
        decoded_response = response.data.decode("utf-8")
        _jresp = json.loads(decoded_response)
        _docs = _jresp.get("response", {}).pop("docs", [])
        logger.info("ads_query_response json", extra={"ads_query_response": _jresp})
        logger.info(
            "ads_query_response", extra={"size": sys.getsizeof(decoded_response)}
        )
        dynamodb.Table(os.environ["SEARCH_CACHE_TABLE_NAME"]).put_item(
            Item={
                "url": url,
                "response": decoded_response,
            }
        )
    jresp = json.loads(decoded_response)
    logger.info("ads_query_response", extra={"ads_query_response": jresp})
    return [
        Pub(
            title=p.get("title", [None])[0],
            pdate=p.get("pubdate"),
            bibcodes=[p.get("bibcode")] + p.get("alternate_bibcode", []),
            abstract=p.get("abstract"),
            dois=[doi.lower() for doi in p["doi"]] if p.get("doi") else None,
        )
        for p in jresp.get("response", {}).get("docs", [])
    ]


def search_ads_dois(dois: list[str]) -> dict[str, str]:
    doi2ads: dict[str, str] = {}
    if not dois:
        return doi2ads

    for i in range(0, len(dois), 100):
        batch_dois = dois[i : i + 100]
        dyndb_response = dynamodb.batch_get_item(
            RequestItems={
                os.environ["DOI2ADS_TABLE_NAME"]: {
                    "Keys": [{"doi": doi} for doi in batch_dois]
                }
            }
        )
        for resp in dyndb_response.get("Responses", {}).get(
            os.environ["DOI2ADS_TABLE_NAME"], []
        ):
            doi2ads[str(resp["doi"]).lower()] = str(resp["bibcode"])
    base_url = (
        "https://api.adsabs.harvard.edu/v1/search/query"
        "?fl=bibcode,doi,alternate_bibcode"
        "&rows=2000"
        "&q="
    )
    dois_temp: set[str] = set()
    unknown_dois = set(dois) - set(doi2ads.keys())
    for i, doi in enumerate(unknown_dois):
        if (
            i == len(unknown_dois) - 1
            or len(base_url + " OR ".join([f"doi:{d}" for d in dois_temp | {doi}]))
            > 12000
            or len(dois_temp) >= 2000
        ):
            if i == len(unknown_dois) - 1:
                dois_temp.add(doi)
            url = base_url + " OR ".join([f"doi:{d}" for d in dois_temp])
            logger.info("search_dois_url length: %s, %s", len(url), url)
            pubmed_response = http.request(
                method="GET",
                url=url,
                headers={"Authorization": f"Bearer {nasa_ads_token}"},
            )
            decoded_response = pubmed_response.data.decode("utf-8")
            data = json.loads(decoded_response)
            docs = data.get("response", {}).get("docs", [])
            doi2ads |= {
                doi: bibcode
                for doc in docs
                for doi in doc.get("doi", [])
                for bibcode in [doc.get("bibcode")] + doc.get("alternate_bibcode", [])
            }
            dois_temp = {doi}
        else:
            dois_temp.add(doi)
    if False:
        with dynamodb.Table(os.environ["DOI2ADS_TABLE_NAME"]).batch_writer() as batch:
            for doi in unknown_dois | set(doi2ads.keys()) - set(dois):
                batch.put_item(Item={"doi": doi.lower(), "ads": doi2ads.get(doi)})
    logger.info("search_ads_dois", extra={"doi2ads": doi2ads})
    logger.info(
        "doi_no_ads_found",
        extra={"doi_no_ads_found": len(set(dois) - set(doi2ads.keys()))},
    )
    return {doi: ads for doi, ads in doi2ads.items() if ads is not None}
