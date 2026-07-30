from __future__ import annotations

import re
from urllib.parse import quote, quote_plus

import httpx


EUROPE_PMC_API_URL = (
    "https://www.ebi.ac.uk/"
    "europepmc/webservices/rest/search"
)


def clean_topic(
    research_topic: str,
) -> str:
    """Prepare a topic for Europe PMC."""

    return " ".join(
        research_topic
        .replace("-", " ")
        .split()
    )


def extract_europe_pmc_authors(
    result: dict,
) -> list[str]:
    """Extract author names from one Europe PMC result."""

    author_list = (
        result.get("authorList")
        or {}
    )

    authors = []

    for author in author_list.get(
        "author",
        [],
    ):
        full_name = str(
            author.get("fullName", "")
        ).strip()

        if full_name:
            authors.append(full_name)

    return authors


def extract_publication_date(
    result: dict,
) -> str:
    """Extract the best publication date available."""

    for field_name in (
        "firstPublicationDate",
        "electronicPublicationDate",
    ):
        date_value = str(
            result.get(
                field_name,
                "",
            )
        ).strip()

        if date_value:
            return date_value

    journal_info = (
        result.get("journalInfo")
        or {}
    )

    print_date = str(
        journal_info.get(
            "printPublicationDate",
            "",
        )
    ).strip()

    if print_date:
        return print_date

    publication_year = str(
        result.get("pubYear", "")
    ).strip()

    return (
        publication_year
        if publication_year
        else "Unknown"
    )


def normalize_doi(doi: str) -> str:
    """Normalize a DOI string."""

    cleaned = doi.strip().lower()

    return re.sub(
        r"^https?://(?:dx\.)?doi\.org/",
        "",
        cleaned,
    )


async def search_europe_pmc(
    research_topic: str,
    max_results: int = 10,
) -> list[dict]:
    """Search Europe PMC and prefer its stable article pages."""

    query = clean_topic(
        research_topic
    )

    if not query:
        return []

    parameters = {
        "query": f"{query} sort_date:y",
        "format": "json",
        "pageSize": max(
            1,
            min(max_results, 50),
        ),
        "resultType": "core",
    }

    headers = {
        "User-Agent": (
            "ResearchPaperAlertBot/1.0 "
            "(personal educational project)"
        )
    }

    async with httpx.AsyncClient(
        timeout=30,
        follow_redirects=True,
        headers=headers,
    ) as client:
        response = await client.get(
            EUROPE_PMC_API_URL,
            params=parameters,
        )

        response.raise_for_status()

    results = (
        response.json()
        .get("resultList", {})
        .get("result", [])
    )

    papers = []

    for result in results:
        title = " ".join(
            str(
                result.get("title", "")
            ).split()
        )

        result_id = str(
            result.get("id", "")
        ).strip()

        result_source = str(
            result.get("source", "")
        ).strip().upper()

        if not title or not result_id:
            continue

        doi = normalize_doi(
            str(
                result.get("doi", "")
            )
        )

        pmcid = str(
            result.get("pmcid", "")
        ).strip()

        pmid = str(
            result.get("pmid", "")
        ).strip()

        if pmcid:
            europe_pmc_url = (
                "https://europepmc.org/"
                f"article/PMC/{quote(pmcid)}"
            )
        else:
            europe_pmc_url = (
                "https://europepmc.org/article/"
                f"{quote(result_source or 'MED')}/"
                f"{quote(result_id)}"
            )

        if doi:
            canonical_url = (
                f"https://doi.org/{doi}"
            )
            paper_key = f"doi:{doi}"
        elif pmcid:
            canonical_url = (
                europe_pmc_url
            )
            paper_key = (
                f"pmcid:{pmcid.lower()}"
            )
        elif pmid:
            canonical_url = (
                europe_pmc_url
            )
            paper_key = f"pmid:{pmid}"
        else:
            canonical_url = (
                europe_pmc_url
            )
            paper_key = (
                "europe-pmc:"
                f"{result_source.lower()}:"
                f"{result_id.lower()}"
            )

        links = [
            (
                "Open Europe PMC record",
                europe_pmc_url,
            )
        ]

        if pmid:
            links.append(
                (
                    "Open PubMed record",
                    "https://pubmed.ncbi.nlm.nih.gov/"
                    f"{quote(pmid)}/",
                )
            )

        if doi:
            links.append(
                (
                    "Open DOI / publisher",
                    f"https://doi.org/{doi}",
                )
            )

        links.append(
            (
                "Search Europe PMC by title",
                "https://europepmc.org/search"
                f"?query={quote_plus(title)}",
            )
        )

        papers.append(
            {
                "paper_key": paper_key,
                "title": title,
                "authors": (
                    extract_europe_pmc_authors(
                        result
                    )
                ),
                "published": (
                    extract_publication_date(
                        result
                    )
                ),
                "url": canonical_url,
                "source": "Europe PMC",
                "links": links,
            }
        )

    return papers
