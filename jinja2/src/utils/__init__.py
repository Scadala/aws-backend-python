from dataclasses import dataclass


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


def order_pubs(
    cr_pubs: list[Pub], pubmed_pubs: list[Pub], ads_pubs: list[Pub]
) -> list[Pub]:
    """
    The order of pubs is determined by the following rules:
        The order of CR Results is preserved.
        If a PubMed Result has a DOI that matches a CR Result, it is merged with the corresponding CR Pub.
        The rest of the PubMed Results are placed inbetween the CR Results, in the order they appear in the PubMed Results.
        If an ADS Result has a DOI that matches a CR Result, it is merged with the corresponding CR Pub.
        The rest of the ADS Results are placed inbetween the CR Results, in the order they appear in the ADS Results.
    Example
    -------
    >>> cr_pubs = [
    ...     Pub(title="cr1", dois=["cr1"]),
    ...     Pub(title="cr2", dois=["cr2"]),
    ...     Pub(title="cr3", dois=["cr3"]),
    ...     Pub(title="cr4", dois=["cr4"]),
    ... ]
    >>> pubmed_pubs = [
    ...     Pub(title="pm1", dois=[]),
    ...     Pub(title="pm2", dois=["cr2"]),
    ...     Pub(title="pm3", dois=[]),
    ...     Pub(title="pm4", dois=["cr1"]),
    ... ]
    >>> ads_pubs = [
    ...     Pub(title="ads1", dois=[]),
    ...     Pub(title="ads2", dois=["cr1"]),
    ...     Pub(title="ads3", dois=["cr2"]),
    ... ]
    >>> [p.title for p in order_pubs(cr_pubs, pubmed_pubs, ads_pubs)]
    ['pm1', 'ads1', 'cr1', 'pm3', 'cr2', 'cr3', 'cr4']
    """

    n_inserted = 0
    doi_ix = {doi: i for i, pub in enumerate(cr_pubs) for doi in pub.dois or []}
    pmid_ix = {
        min(doi_ix[doi] for doi in pm.dois if doi in doi_ix)
        for pm in pubmed_pubs
        if pm.dois and any(doi in doi_ix for doi in pm.dois)
    }
    for pm in pubmed_pubs:
        if pm.dois and any(doi in doi_ix for doi in pm.dois):
            cr_pub = cr_pubs[doi_ix[next(doi for doi in pm.dois if doi in doi_ix)]]
            cr_pub.pmids = pm.pmids
            cr_pub.abstract = cr_pub.abstract or pm.abstract
            cr_pub.title = cr_pub.title or pm.title
            cr_pub.pdate = cr_pub.pdate or pm.pdate
            pmid_ix -= {min(pmid_ix)}
        else:
            cr_pubs.insert(min(pmid_ix) + n_inserted if pmid_ix else len(cr_pubs), pm)
            n_inserted += 1

    n_inserted = 0
    doi_ix = {doi: i for i, pub in enumerate(cr_pubs) for doi in pub.dois or []}
    ads_ix = {
        min(doi_ix[doi] for doi in ad.dois if doi in doi_ix)
        for ad in ads_pubs
        if ad.dois and any(doi in doi_ix for doi in ad.dois)
    }
    for ad in ads_pubs:
        if ad.dois and any(doi in doi_ix for doi in ad.dois):
            cr_pub = cr_pubs[doi_ix[next(doi for doi in ad.dois if doi in doi_ix)]]
            cr_pub.bibcodes = ad.bibcodes
            cr_pub.abstract = cr_pub.abstract or ad.abstract
            cr_pub.title = cr_pub.title or ad.title
            cr_pub.pdate = cr_pub.pdate or ad.pdate
            ads_ix -= {min(ads_ix)}
        else:
            cr_pubs.insert(min(ads_ix) + n_inserted if ads_ix else len(cr_pubs), ad)
            n_inserted += 1

    return cr_pubs
