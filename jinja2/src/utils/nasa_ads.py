import boto3

from . import Pub
import simplejson as json
import logging
import urllib3

http = urllib3.PoolManager(headers={"User-Agent": "georgwendorf@gmail.com"})


logger = logging.getLogger(__name__)

ssm_client = boto3.client("ssm", region_name="eu-central-1")

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
