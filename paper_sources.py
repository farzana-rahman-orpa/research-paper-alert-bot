from __future__ import annotations

import asyncio
import os
import re
from collections.abc import Awaitable

from arxiv_client import search_arxiv
from crossref_client import search_crossref
from europe_pmc_client import (
    search_europe_pmc,
)
from paper_link_utils import merge_links
from semantic_scholar_client import (
    search_semantic_scholar,
)


SOURCE_PRIORITY = {
    "Europe PMC": 1,
    "Crossref": 2,
    "Semantic Scholar": 3,
    "arXiv": 4,
}


def normalize_title(
    title: str,
) -> str:
    """Create a simplified title for duplicate detection."""

    return re.sub(
        r"[^a-z0-9]+",
        "",
        title.lower(),
    )


def publication_sort_value(
    paper: dict,
) -> str:
    """Convert publication text into a sortable value."""

    published = str(
        paper.get("published", "")
    ).strip()

    year_match = re.match(
        r"^(\d{4})",
        published,
    )

    if not year_match:
        return "0000-00-00"

    year = year_match.group(1)

    if re.fullmatch(
        r"\d{4}-\d{2}-\d{2}",
        published,
    ):
        return published

    if re.fullmatch(
        r"\d{4}-\d{2}",
        published,
    ):
        return f"{published}-01"

    return f"{year}-01-01"


def is_better_duplicate(
    candidate: dict,
    existing: dict,
) -> bool:
    """Choose the preferred metadata source for a duplicate."""

    candidate_priority = (
        SOURCE_PRIORITY.get(
            str(
                candidate.get(
                    "source",
                    "",
                )
            ),
            99,
        )
    )

    existing_priority = (
        SOURCE_PRIORITY.get(
            str(
                existing.get(
                    "source",
                    "",
                )
            ),
            99,
        )
    )

    return (
        candidate_priority
        < existing_priority
    )


def combine_duplicate_records(
    preferred: dict,
    other: dict,
) -> dict:
    """Keep preferred metadata while preserving every useful link."""

    combined = dict(preferred)

    combined["links"] = merge_links(
        preferred.get("links") or [],
        other.get("links") or [],
    )

    if not combined.get("authors"):
        combined["authors"] = (
            other.get("authors")
            or []
        )

    if (
        combined.get("published")
        in (None, "", "Unknown")
    ):
        combined["published"] = (
            other.get("published")
            or "Unknown"
        )

    return combined


def remove_duplicate_papers(
    papers: list[dict],
) -> list[dict]:
    """Remove duplicate records while merging their backup links."""

    unique_papers: list[dict] = []

    for paper in papers:
        paper_key = str(
            paper.get("paper_key", "")
        ).strip().lower()

        title_key = normalize_title(
            str(
                paper.get("title", "")
            )
        )

        duplicate_index = None

        for index, existing in enumerate(
            unique_papers
        ):
            existing_key = str(
                existing.get(
                    "paper_key",
                    "",
                )
            ).strip().lower()

            existing_title = (
                normalize_title(
                    str(
                        existing.get(
                            "title",
                            "",
                        )
                    )
                )
            )

            same_key = bool(
                paper_key
                and existing_key
                and paper_key
                == existing_key
            )

            same_title = bool(
                title_key
                and existing_title
                and title_key
                == existing_title
            )

            if same_key or same_title:
                duplicate_index = index
                break

        if duplicate_index is None:
            unique_papers.append(
                paper
            )
            continue

        existing = unique_papers[
            duplicate_index
        ]

        if is_better_duplicate(
            paper,
            existing,
        ):
            unique_papers[
                duplicate_index
            ] = (
                combine_duplicate_records(
                    paper,
                    existing,
                )
            )
        else:
            unique_papers[
                duplicate_index
            ] = (
                combine_duplicate_records(
                    existing,
                    paper,
                )
            )

    unique_papers.sort(
        key=publication_sort_value,
        reverse=True,
    )

    return unique_papers


async def run_source(
    source_name: str,
    search_operation: Awaitable[
        list[dict]
    ],
) -> tuple[
    str,
    list[dict],
    str | None,
]:
    """Run one paper source and capture its error safely."""

    try:
        papers = await search_operation

        print(
            f"{source_name} returned "
            f"{len(papers)} paper(s)."
        )

        return (
            source_name,
            papers,
            None,
        )

    except Exception as error:
        error_text = str(error)

        print(
            f"{source_name} search failed: "
            f"{error_text}"
        )

        return (
            source_name,
            [],
            error_text,
        )


async def search_all_sources(
    research_topic: str,
    max_results_per_source: int = 10,
) -> tuple[list[dict], set[str]]:
    """Search all available sources and return successful source names."""

    search_tasks = [
        run_source(
            "arXiv",
            search_arxiv(
                research_topic,
                max_results=(
                    max_results_per_source
                ),
            ),
        ),
        run_source(
            "Crossref",
            search_crossref(
                research_topic,
                max_results=(
                    max_results_per_source
                ),
            ),
        ),
        run_source(
            "Europe PMC",
            search_europe_pmc(
                research_topic,
                max_results=(
                    max_results_per_source
                ),
            ),
        ),
    ]

    semantic_key = os.getenv(
        "SEMANTIC_SCHOLAR_API_KEY",
        "",
    ).strip()

    if semantic_key:
        search_tasks.append(
            run_source(
                "Semantic Scholar",
                search_semantic_scholar(
                    research_topic,
                    max_results=(
                        max_results_per_source
                    ),
                ),
            )
        )
    else:
        print(
            "Semantic Scholar skipped: "
            "API key is not configured."
        )

    source_results = await asyncio.gather(
        *search_tasks
    )

    combined_papers: list[dict] = []
    successful_sources: set[str] = set()

    for (
        source_name,
        papers,
        error,
    ) in source_results:
        if error is None:
            successful_sources.add(
                source_name
            )

        combined_papers.extend(
            papers
        )

    if not successful_sources:
        raise RuntimeError(
            "All research-paper sources failed."
        )

    unique_papers = (
        remove_duplicate_papers(
            combined_papers
        )
    )

    print(
        "Combined unique papers: "
        f"{len(unique_papers)}"
    )

    return (
        unique_papers,
        successful_sources,
    )
