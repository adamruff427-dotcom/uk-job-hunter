"""Opt-in UK discovery on large Greenhouse boards without oversized full feeds."""
from __future__ import annotations

import time
from .providers import endpoint, normalized, read_ats_json
from .source_health import FeedResult, SourceError
from .uk_scope import obviously_non_uk, has_uk_location


def bounded(source, key, default, lower, upper):
    value = source.get(key, default)
    if type(value) is not int or not lower <= value <= upper:
        raise ValueError('Invalid source budget')
    return value


def fetch_greenhouse_details(source, *, timeout=15, reader=None, sleep=time.sleep, clock=time.monotonic):
    reader = reader or read_ats_json
    cap = bounded(source, 'max_details', 25, 0, 50)
    seconds = bounded(source, 'max_seconds', 60, 1, 120)
    budget = bounded(source, 'max_total_bytes', 20_000_000, 1_000, 30_000_000)
    deadline = clock() + seconds
    base = endpoint('greenhouse', source['board']).split('?')[0]
    obj, _, unchanged, used = reader(base, timeout=min(timeout, seconds), max_bytes=min(10_000_000, budget))
    if unchanged or not isinstance(obj, dict) or not isinstance(obj.get('jobs'), list):
        raise SourceError('schema_error')
    list_count = len(obj['jobs'])
    received = used
    jobs, seen = [], set()
    for item in obj['jobs']:
        if not isinstance(item, dict) or type(item.get('id')) is not int or item['id'] < 1:
            raise SourceError('schema_error')
        if not isinstance(item.get('location'), dict):
            raise SourceError('schema_error')
        record = normalized(source['name'], 'greenhouse', source['board'], item)
        if not record:
            raise SourceError('schema_error')
        if obviously_non_uk(record['location']) or item['id'] in seen:
            continue
        seen.add(item['id'])
        record['detail_status'] = 'metadata_only'
        if has_uk_location(record['location']):
            record['country'] = 'GB'
        jobs.append((item['id'], record))
    # Prioritize explicit UK postings, but retain every ambiguous vacancy in
    # discovery even when details cannot be retrieved within this refresh.
    jobs.sort(key=lambda pair: (pair[1].get('country') != 'GB', pair[0]))
    attempts, succeeded, failed = 0, 0, 0
    detail_error = {}
    for identifier, record in jobs:
        remaining = deadline - clock()
        allowance = min(1_000_000, budget - used)
        if attempts >= cap or remaining <= 0.5 or allowance < 1:
            break
        sleep(0.5)
        remaining = deadline - clock()
        if remaining <= 0:
            break
        attempts += 1
        try:
            obj, _, unchanged, size = reader(base + '/' + str(identifier), timeout=min(timeout, remaining), max_bytes=allowance)
            used += size
            received += size
            if unchanged or not isinstance(obj, dict) or obj.get('id') != identifier:
                raise SourceError('schema_error')
            detail = normalized(source['name'], 'greenhouse', source['board'], obj)
            if not detail or not detail['description']:
                raise SourceError('schema_error')
            # The list provides scope and identity; details enrich only this
            # validated ID, never a URL embedded in an advert.
            record['description'] = detail['description']
            record['detail_status'] = 'complete'
            succeeded += 1
        except SourceError as exc:
            detail_error = {'detail_error_category': exc.category, 'detail_http_status': exc.http_status,
                            'retry_after_seconds': exc.retry_after}
            failed += 1
            record['detail_status'] = 'unavailable'
            # Account conservatively for unknown/aborted response sizes.
            used += allowance
            if exc.retryable or exc.category == 'access_denied':
                break
    pending = len(jobs) - succeeded
    return FeedResult([record for _, record in jobs], complete=pending == 0,
                      list_count=list_count,
                      details_attempted=attempts, details_succeeded=succeeded,
                      details_failed=failed, details_pending=pending,
                      response_bytes=received, budget_bytes_used=used,
                      error_category='partial_details' if pending else None, **detail_error)
