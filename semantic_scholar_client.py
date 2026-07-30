from __future__ import annotations

import asyncio
import os
import re
from urllib.parse import quote

import httpx
from dotenv import load_dotenv


load_dotenv()

SEMANTIC_SCHOLAR_API_URL = (
    "https://api.semanticscholar.org/"
    "graph/v1/paper/search"
)

MAX_RETRIES = 3
DEFAULT_RETRY_SECONDS = 15


def clean_semantic_scholar_query(
    research_topic: str,
) -> str:
    """Prepare a plain-text Semantic Scholar query."""

    return " ".join(
        research_topic
        .replace("-", " ")
        .split()
    )


def normalize_arxiv_id(
    arxiv_id: str,
) -> str:
    """Remove an arXiv version suffix."""

    return re.sub(
        r"v\d+$",
        "",
        arxiv_id.strip(),
        flags=re.IGNORECASE,
    )


def get_retry_delay(
    response: httpx.Response,
    attempt_number: int,
) -> float:
    """Read Retry-After or use increasing delays."""

    retry_after = response.headers.get(
        "Retry-After",
        "",
    ).strip()

    try:
        return max(
            float(retry_after),
            1.0,
        )
    except ValueError:
        return (
            DEFAULT_RETRY_SECONDS
            * attempt_number
        )


async def search_semantic_scholar(
    research_topic: str,
    max_results: int = 10,
) -> list[dict]:
    """Search Semantic Scholar when a key is configured."""

    query = clean_semantic_scholar_query(
        research_topic
    )

    if not query:
        return []

    parameters = {
        "query": query,
        "limit": max(
            1,
            min(max_results, 100),
        ),
        "fields": (
            "paperId,title,authors,year,"
            "publicationDate,url,externalIds"
        ),
    }

    headers = {
        "User-Agent": (
            "ResearchPaperAlertBot/1.0 "
            "(personal educational project)"
        )
    }

    api_key = os.getenv(
        "SEMANTIC_SCHOLAR_API_KEY",
        "",
    ).strip()

    if api_key:
        headers["x-api-key"] = api_key

    response_data = None

    async with httpx.AsyncClient(
        timeout=30,
        follow_redirects=True,
        headers=headers,
    ) as client:
        for attempt in range(
            1,
            MAX_RETRIES + 1,
        ):
            response = await client.get(
                SEMANTIC_SCHOLAR_API_URL,
                params=parameters,
            )

            if response.status_code != 429:
                response.raise_for_status()
                response_data = (
                    response.json()
                )
                break

            if attempt == MAX_RETRIES:
                raise RuntimeError(
                    "Semantic Scholar rate limit "
                    "remained active after retries."
                )

            retry_delay = get_retry_delay(
                response,
                attempt,
            )

            print(
                "Semantic Scholar rate limit. "
                f"Retrying in {retry_delay:.0f}s."
            )

            await asyncio.sleep(
                retry_delay
            )

    if response_data is None:
        return []

    papers = []

    for result in response_data.get(
        "data",
        [],
    ):
        title = " ".join(
            str(
                result.get("title", "")
            ).split()
        )

        paper_id = str(
            result.get("paperId", "")
        ).strip()

        if not title or not paper_id:
            continue

        authors = [
            str(
                author.get("name", "")
            ).strip()
            for author in result.get(
                "authors",
                [],
            )
            if str(
                author.get("name", "")
            ).strip()
        ]

        external_ids = (
            result.get("externalIds")
            or {}
        )

        arxiv_id = str(
            external_ids.get("ArXiv", "")
        ).strip()

        doi = str(
            external_ids.get("DOI", "")
        ).strip().lower()

        semantic_url = str(
            result.get("url", "")
        ).strip()

        if not semantic_url:
            semantic_url = (
                "https://www.semanticscholar.org/"
                f"paper/{quote(paper_id)}"
            )

        links = [
            (
                "Open Semantic Scholar",
                semantic_url,
            )
        ]

        if arxiv_id:
            normalized_arxiv_id = (
                normalize_arxiv_id(
                    arxiv_id
                )
            )

            canonical_url = (
                "https://arxiv.org/abs/"
                f"{normalized_arxiv_id}"
            )

            paper_key = (
                "arxiv:"
                f"{normalized_arxiv_id.lower()}"
            )

            links.append(
                (
                    "Open arXiv record",
                    canonical_url,
                )
            )

        elif doi:
            canonical_url = (
                f"https://doi.org/{doi}"
            )

            paper_key = f"doi:{doi}"

            links.append(
                (
                    "Open DOI / publisher",
                    canonical_url,
                )
            )

        else:
            canonical_url = (
                semantic_url
            )

            paper_key = (
                "semantic-scholar:"
                f"{paper_id.lower()}"
            )

        publication_date = str(
            result.get(
                "publicationDate",
                "",
            )
            or ""
        ).strip()

        year = result.get("year")

        published = (
            publication_date
            or (
                str(year)
                if year
                else "Unknown"
            )
        )

        papers.append(
            {
                "paper_key": paper_key,
                "title": title,
                "authors": authors,
                "published": published,
                "url": canonical_url,
                "source": (
                    "Semantic Scholar"
                ),
                "links": links,
            }
        )

    return papers
