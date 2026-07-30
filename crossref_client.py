from __future__ import annotations

import html
import os
import re
from urllib.parse import quote, quote_plus

import httpx
from dotenv import load_dotenv


load_dotenv()

CROSSREF_API_URL = (
    "https://api.crossref.org/works"
)


def clean_text(value: str) -> str:
    """Remove HTML tags and normalize spaces."""

    without_tags = re.sub(
        r"<[^>]+>",
        " ",
        value,
    )

    return " ".join(
        html.unescape(
            without_tags
        ).split()
    )


def extract_crossref_date(
    item: dict,
) -> str:
    """Extract the best available publication date."""

    date_fields = (
        "published-online",
        "published-print",
        "published",
        "issued",
        "created",
    )

    for field_name in date_fields:
        date_object = (
            item.get(field_name)
            or {}
        )

        date_parts_list = (
            date_object.get("date-parts")
            or []
        )

        if not date_parts_list:
            continue

        date_parts = date_parts_list[0]

        if not date_parts:
            continue

        year = int(date_parts[0])

        if len(date_parts) >= 3:
            return (
                f"{year:04d}-"
                f"{int(date_parts[1]):02d}-"
                f"{int(date_parts[2]):02d}"
            )

        if len(date_parts) >= 2:
            return (
                f"{year:04d}-"
                f"{int(date_parts[1]):02d}-01"
            )

        return str(year)

    return "Unknown"


def extract_crossref_authors(
    item: dict,
) -> list[str]:
    """Extract author names from one Crossref item."""

    authors = []

    for author in item.get(
        "author",
        [],
    ):
        given_name = str(
            author.get("given", "")
        ).strip()

        family_name = str(
            author.get("family", "")
        ).strip()

        full_name = " ".join(
            part
            for part in (
                given_name,
                family_name,
            )
            if part
        )

        if full_name:
            authors.append(full_name)

    return authors


async def search_crossref(
    research_topic: str,
    max_results: int = 10,
) -> list[dict]:
    """Search Crossref and include a stable metadata-search fallback."""

    cleaned_topic = " ".join(
        research_topic.split()
    )

    if not cleaned_topic:
        return []

    contact_email = os.getenv(
        "CROSSREF_CONTACT_EMAIL",
        "",
    ).strip()

    parameters = {
        "query.bibliographic": (
            cleaned_topic
        ),
        "rows": max(
            1,
            min(max_results, 50),
        ),
        "sort": "published",
        "order": "desc",
        "select": (
            "DOI,title,author,published,"
            "published-online,published-print,"
            "issued,created,URL,type,"
            "container-title"
        ),
    }

    if contact_email:
        parameters["mailto"] = (
            contact_email
        )

    user_agent = (
        "ResearchPaperAlertBot/1.0 "
        "(personal educational project"
    )

    if contact_email:
        user_agent += (
            f"; mailto:{contact_email}"
        )

    user_agent += ")"

    async with httpx.AsyncClient(
        timeout=30,
        follow_redirects=True,
        headers={
            "User-Agent": user_agent,
        },
    ) as client:
        response = await client.get(
            CROSSREF_API_URL,
            params=parameters,
        )

        response.raise_for_status()

    items = (
        response.json()
        .get("message", {})
        .get("items", [])
    )

    papers = []

    for item in items:
        titles = item.get("title") or []

        if not titles:
            continue

        title = clean_text(
            str(titles[0])
        )

        doi = str(
            item.get("DOI", "")
        ).strip().lower()

        if not title or not doi:
            continue

        doi_url = (
            f"https://doi.org/{doi}"
        )

        crossref_search_url = (
            "https://search.crossref.org/"
            f"?q={quote_plus(title)}"
        )

        crossref_metadata_url = (
            "https://api.crossref.org/works/"
            f"{quote(doi, safe='')}"
        )

        papers.append(
            {
                "paper_key": f"doi:{doi}",
                "title": title,
                "authors": (
                    extract_crossref_authors(
                        item
                    )
                ),
                "published": (
                    extract_crossref_date(
                        item
                    )
                ),
                "url": doi_url,
                "source": "Crossref",
                "links": [
                    (
                        "Search Crossref metadata",
                        crossref_search_url,
                    ),
                    (
                        "Open DOI / publisher",
                        doi_url,
                    ),
                    (
                        "View raw Crossref record",
                        crossref_metadata_url,
                    ),
                ],
            }
        )

    return papers
