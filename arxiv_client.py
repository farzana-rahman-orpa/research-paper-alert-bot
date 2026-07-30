from __future__ import annotations

import re

import feedparser
import httpx


ARXIV_API_URL = "https://export.arxiv.org/api/query"

STOP_WORDS = {
    "a",
    "an",
    "and",
    "for",
    "in",
    "of",
    "on",
    "the",
    "to",
    "with",
}


def build_search_query(research_topic: str) -> str:
    """Convert the user's topic into an arXiv query."""

    words = re.findall(
        r"[A-Za-z0-9-]+",
        research_topic.lower(),
    )

    important_words = [
        word
        for word in words
        if word not in STOP_WORDS
    ]

    if not important_words:
        important_words = words

    important_words = important_words[:8]

    return " AND ".join(
        f"all:{word}"
        for word in important_words
    )


def normalize_arxiv_id(arxiv_id: str) -> str:
    """Remove an arXiv version suffix such as v1."""

    return re.sub(
        r"v\d+$",
        "",
        arxiv_id.strip(),
        flags=re.IGNORECASE,
    )


async def search_arxiv(
    research_topic: str,
    max_results: int = 10,
) -> list[dict]:
    """Search arXiv and return standardized paper records."""

    search_query = build_search_query(
        research_topic
    )

    if not search_query:
        return []

    parameters = {
        "search_query": search_query,
        "start": 0,
        "max_results": max(
            1,
            min(max_results, 50),
        ),
        "sortBy": "submittedDate",
        "sortOrder": "descending",
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
    ) as client:
        response = await client.get(
            ARXIV_API_URL,
            params=parameters,
            headers=headers,
        )

        response.raise_for_status()

    feed = feedparser.parse(
        response.text
    )

    papers = []

    for entry in feed.entries:
        title = " ".join(
            str(
                entry.get("title", "")
            ).split()
        )

        if not title:
            continue

        entry_id = str(
            entry.get("id", "")
        ).strip()

        raw_arxiv_id = (
            entry_id.rstrip("/").split("/")[-1]
        )

        arxiv_id = normalize_arxiv_id(
            raw_arxiv_id
        )

        if not arxiv_id:
            continue

        authors = [
            str(
                author.get("name", "")
            ).strip()
            for author in entry.get(
                "authors",
                [],
            )
            if str(
                author.get("name", "")
            ).strip()
        ]

        published = str(
            entry.get("published", "")
        )[:10] or "Unknown"

        abstract_url = (
            f"https://arxiv.org/abs/{arxiv_id}"
        )

        pdf_url = (
            f"https://arxiv.org/pdf/{arxiv_id}"
        )

        papers.append(
            {
                "paper_key": (
                    f"arxiv:{arxiv_id.lower()}"
                ),
                "title": title,
                "authors": authors,
                "published": published,
                "url": abstract_url,
                "source": "arXiv",
                "links": [
                    (
                        "Open arXiv record",
                        abstract_url,
                    ),
                    (
                        "Open PDF",
                        pdf_url,
                    ),
                ],
            }
        )

    return papers
