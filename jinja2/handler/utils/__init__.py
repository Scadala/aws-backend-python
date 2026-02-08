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
