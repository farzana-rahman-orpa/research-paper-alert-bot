from __future__ import annotations

from typing import Iterable


def merge_links(
    *link_groups: Iterable[tuple[str, str]],
) -> list[tuple[str, str]]:
    """Merge labelled links while removing duplicate URLs."""

    merged: list[tuple[str, str]] = []
    seen_urls: set[str] = set()

    for group in link_groups:
        for label, url in group:
            clean_label = str(label).strip()
            clean_url = str(url).strip()

            if not clean_label or not clean_url:
                continue

            if clean_url in seen_urls:
                continue

            seen_urls.add(clean_url)
            merged.append((clean_label, clean_url))

    return merged


def format_paper_links(paper: dict) -> str:
    """Create a readable group of primary and backup paper links."""

    links = paper.get("links") or []

    if not links:
        fallback_url = str(paper.get("url", "")).strip()

        if fallback_url:
            links = [("Open paper", fallback_url)]

    if not links:
        return "Links: unavailable"

    lines = []

    for index, link_item in enumerate(links):
        try:
            label, url = link_item
        except (TypeError, ValueError):
            continue

        prefix = "🔗" if index == 0 else "↪️"
        lines.append(f"{prefix} {label}: {url}")

    if not lines:
        return "Links: unavailable"

    return "\n".join(lines)
