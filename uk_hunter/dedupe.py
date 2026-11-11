"""Conservative cross-source deduplication without merging distinct ATS posts."""
from __future__ import annotations

import re


def _canon(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").casefold()).strip()


def unique_jobs(jobs: list[dict]) -> list[dict]:
    """Prefer direct employer sources over aggregators for the same vacancy.

    Distinct vacancies from one provider are never merged merely because their
    title matches; two genuine Risk Manager requisitions may coexist.
    """
    rank = {"greenhouse": 0, "ashby": 0, "lever": 0, "smartrecruiters": 0, "website": 1, "adzuna": 2, "reed": 2}
    ordered = sorted(jobs, key=lambda x: rank.get(x.get("source"), 3))
    output: list[dict] = []
    seen_ids: set[str] = set()
    seen_urls: dict[str, set[str]] = {}
    seen_triplets: dict[tuple[str, str, str], set[str]] = {}
    for job in ordered:
        identifier = str(job.get("id") or "")
        url = str(job.get("url") or "")
        if identifier and identifier in seen_ids:
            continue
        source = str(job.get("source") or "unknown")
        if url and url in seen_urls and source not in seen_urls[url]:
            continue
        triplet = tuple(_canon(job.get(k)) for k in ("company", "title", "location"))
        # Triplets can only identify a duplicate across different sources,
        # and only when all fields are known.
        if all(triplet) and triplet in seen_triplets and source not in seen_triplets[triplet]:
            continue
        output.append(job)
        if identifier:
            seen_ids.add(identifier)
        if url:
            seen_urls.setdefault(url, set()).add(source)
        if all(triplet):
            seen_triplets.setdefault(triplet, set()).add(source)
    return output
