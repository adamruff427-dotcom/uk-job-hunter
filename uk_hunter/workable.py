"""Workable's documented public jobs widget, using its canonical GET route."""
from __future__ import annotations

import re
from .providers import read_ats_json, plain, valid_job_link, iso_date
from .source_health import FeedResult, SourceError

UK_CODES = {'gb', 'gbr', 'uk', 'united kingdom', 'great britain'}


def fetch_workable(source, *, timeout=15, reader=None):
    board = source.get('board')
    if not isinstance(board, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', board):
        raise ValueError('Invalid Workable board identifier')
    reader = reader or read_ats_json
    obj, _, unchanged, size = reader('https://apply.workable.com/api/v1/widget/accounts/' + board + '?details=true', timeout=timeout)
    if unchanged or not isinstance(obj, dict) or not isinstance(obj.get('jobs'), list):
        raise SourceError('schema_error')
    results = []
    for item in obj['jobs']:
        if not isinstance(item, dict):
            raise SourceError('schema_error')
        shortcode = item.get('shortcode')
        url, title = valid_job_link(item.get('url')), item.get('title')
        if not isinstance(shortcode, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', shortcode) or not url or not isinstance(title, str) or not title.strip():
            raise SourceError('schema_error')
        locations = item.get('locations') or []
        if not isinstance(locations, list) or any(not isinstance(loc, dict) for loc in locations):
            raise SourceError('schema_error')
        locations = [loc for loc in locations if loc.get('hidden') is not True]
        if not locations:
            locations = [{k: item.get(k) for k in ('city', 'state', 'country')}]
        places, countries = [], []
        for loc in locations:
            country = str(loc.get('countryCode') or loc.get('country') or '')
            countries.append(country)
            places.append(', '.join(str(loc[k]) for k in ('city', 'region', 'state', 'country') if loc.get(k)) or country)
        country = 'GB' if any(c.casefold() in UK_CODES for c in countries) else countries[0] if all(countries) else None
        description = plain(item.get('description') or '')
        results.append({
            'id': f'workable:{board}:{shortcode}', 'company': source['name'], 'title': title.strip(),
            'url': url, 'location': '; '.join(dict.fromkeys(p for p in places if p)), 'country': country,
            'date': iso_date(item.get('published_on')), 'description': description,
            'detail_status': 'complete' if description else 'metadata_only',
            'uk_eligibility': 'confirmed_uk' if country == 'GB' else 'non_uk' if country else 'unknown',
            'workplace_type': 'remote' if item.get('telecommuting') is True else 'unknown',
            'salary_min': None, 'salary_max': None, 'source': 'workable',
            'occupation': item.get('department') or None,
            'source_metadata': {'department': item.get('department'), 'employment_type': item.get('employment_type')},
        })
    # Widget responses can repeat one shortcode per advertised location. Merge
    # those rows before persistence, retaining every location and UK evidence.
    merged = {}
    for job in results:
        existing = merged.get(job['id'])
        if existing is None:
            merged[job['id']] = job
            continue
        if existing['title'] != job['title']:
            raise SourceError('schema_error')
        existing['location'] = '; '.join(dict.fromkeys(p for value in (existing['location'], job['location']) for p in value.split('; ') if p))
        if 'GB' in (existing['country'], job['country']):
            existing['country'] = 'GB'
        elif not existing['country'] or not job['country']:
            existing['country'] = None
        existing['uk_eligibility'] = 'confirmed_uk' if existing['country'] == 'GB' else 'non_uk' if existing['country'] else 'unknown'
        if existing['workplace_type'] != job['workplace_type']:
            existing['workplace_type'] = 'unknown'
        if not existing['description'] and job['description']:
            existing['description'], existing['detail_status'] = job['description'], job['detail_status']
    return FeedResult(merged.values(), list_count=len(obj['jobs']), response_bytes=size)
