"""Conservative duplicate handling with secondary source attribution."""
from __future__ import annotations

from collections import defaultdict
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

AGGREGATORS = {'adzuna', 'reed'}


def _canon(value: object) -> str:
    return re.sub(r'[^a-z0-9]+', ' ', str(value or '').casefold()).strip()


def _url(value):
    try:
        u = urlsplit(str(value or ''))
        query = [(k, v) for k, v in parse_qsl(u.query, keep_blank_values=True)
                 if not k.lower().startswith('utm_') and k.lower() not in {'gclid', 'fbclid'}]
        return urlunsplit((u.scheme.lower(), u.netloc.lower(), u.path.rstrip('/'), urlencode(sorted(query)), ''))
    except ValueError:
        return str(value or '')


def _triplet(job):
    return tuple(_canon(job.get(k)) for k in ('company', 'title', 'location'))


def unique_jobs(jobs: list[dict]) -> list[dict]:
    """Prefer direct postings, preserving IDs and links for every merged source.

    A title/company/location heuristic is used only for an aggregator copy with
    exactly one matching direct posting. Distinct direct requisitions and ambiguous
    matches stay separate. Canonical URLs can identify a stronger exact match.
    """
    rank = {'greenhouse': 0, 'ashby': 0, 'lever': 0, 'smartrecruiters': 0,
            'website': 1, 'adzuna': 2, 'reed': 2}
    direct_candidates = defaultdict(set)
    for job in jobs:
        if job.get('source') not in AGGREGATORS and all(_triplet(job)):
            direct_candidates[_triplet(job)].add((str(job.get('id') or ''), _url(job.get('url'))))
    output, by_id, by_url, by_triplet = [], {}, {}, {}
    for original in sorted(jobs, key=lambda j: rank.get(j.get('source'), 3)):
        identifier, url = str(original.get('id') or ''), _url(original.get('url'))
        triplet = _triplet(original)
        duplicate = by_id.get(identifier) if identifier else None
        if duplicate is None and url:
            candidate = by_url.get(url)
            if candidate is not None and (candidate.get('source') != original.get('source') or candidate.get('id') == identifier):
                duplicate = candidate
        if duplicate is None and original.get('source') in AGGREGATORS and len(direct_candidates[triplet]) == 1:
            duplicate = by_triplet.get(triplet)
        references = original.get('source_references') or [{'source': original.get('source'), 'url': original.get('url'), 'id': original.get('id')}]
        if duplicate is not None:
            saved = duplicate.setdefault('source_references', [{'source': duplicate.get('source'), 'url': duplicate.get('url'), 'id': duplicate.get('id')}])
            for ref in references:
                if ref not in saved:
                    saved.append(dict(ref))
            if identifier:
                by_id[identifier] = duplicate
            if url:
                by_url[url] = duplicate
            continue
        job = dict(original)
        if original.get('source_references'):
            job['source_references'] = [dict(ref) for ref in references]
        output.append(job)
        if identifier:
            by_id[identifier] = job
        if url:
            by_url[url] = job
        if job.get('source') not in AGGREGATORS and all(triplet):
            by_triplet[triplet] = job
    return output
