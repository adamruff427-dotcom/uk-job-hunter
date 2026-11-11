"""Private SQLite vacancy snapshots and auditable, bounded source refreshes.

Only normalized public vacancy fields are retained. Source configuration, request
URLs, headers, credentials and candidate preferences never enter the database.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import time

from .providers import fetch_feed
from .dedupe import unique_jobs
from .industries import classify
from .uk_scope import obviously_non_uk

SCHEMA_VERSION = 1
FIELDS = {
    'id', 'title', 'company', 'location', 'url', 'date', 'description',
    'workplace_type', 'salary_min', 'salary_max', 'source', 'occupation',
    'country', 'remote_eligibility', 'expires_at', 'salary_currency',
    'salary_period', 'salary_basis', 'source_metadata',
}


def utcnow():
    return datetime.now(timezone.utc).isoformat()


def source_key(source):
    # Queries are part of identity: changing a board's search must not overwrite
    # another snapshot. Only a hash is persisted, never local query/config text.
    safe = {k: source.get(k) for k in ('provider', 'board', 'url', 'queries', 'max_pages', 'results_per_page', 'max_details')}
    return hashlib.sha256(json.dumps(safe, sort_keys=True).encode()).hexdigest()[:24]


def safe_url(value):
    from urllib.parse import urlsplit, urlunsplit
    try:
        u = urlsplit(str(value or ''))
        if u.scheme != 'https' or not u.hostname or u.username or u.password:
            return ''
        # Drop credential-bearing query keys defensively; ordinary posting query
        # identifiers (e.g. gh_jid) must be preserved.
        from urllib.parse import parse_qsl, urlencode
        query = urlencode([(k, v) for k, v in parse_qsl(u.query, keep_blank_values=True)
                           if not any(x in k.lower() for x in ('key', 'token', 'secret', 'password', 'app_id'))])
        return urlunsplit((u.scheme, u.netloc, u.path, query, ''))
    except ValueError:
        return ''


def clean_record(item, source, stamp):
    job = {k: v for k, v in item.items() if k in FIELDS and k != 'source_metadata'}
    if not all(isinstance(job.get(k), str) and job[k] for k in ('id', 'title', 'company')):
        raise ValueError('Invalid normalized vacancy identity')
    job['url'] = safe_url(job.get('url'))
    if not job['url']:
        raise ValueError('Invalid normalized vacancy URL')
    job['source'] = str(source.get('provider', 'unknown'))
    job['industry'], job['industry_basis'] = classify(job, source.get('sector'))
    job['occupation'] = job.get('occupation') or None
    country = str(job.get('country') or '').casefold()
    location = str(job.get('location') or '')
    if country in {'gb', 'gbr', 'uk', 'united kingdom'}:
        eligibility = 'confirmed_uk'
    elif country or obviously_non_uk(location):
        eligibility = 'non_uk'
    else:
        import re
        eligibility = 'confirmed_uk' if re.search(r'\b(UK|United Kingdom|Great Britain)\b', location, re.I) else 'unknown'
    job['uk_eligibility'] = eligibility
    if job.get('salary_min') is not None or job.get('salary_max') is not None:
        job.setdefault('salary_currency', 'GBP')
        job.setdefault('salary_period', 'year')
        job.setdefault('salary_basis', 'advertised')
    else:
        job.setdefault('salary_currency', None)
        job.setdefault('salary_period', None)
        job.setdefault('salary_basis', 'unknown')
    # A tiny allowlist of non-secret upstream metadata, never a raw response.
    metadata = item.get('source_metadata') or {}
    job['source_metadata'] = {k: metadata[k] for k in ('department', 'employment_type', 'salary_is_predicted') if k in metadata}
    job['last_seen'] = stamp
    job['scan_status'] = 'seen'
    return job


class VacancyIndex:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        try:
            fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            pass
        else:
            os.close(fd)
        os.chmod(self.path, 0o600)
        with self.connect() as db:
            version = db.execute('PRAGMA user_version').fetchone()[0]
            if version > SCHEMA_VERSION:
                raise ValueError('Vacancy index was created by a newer version')
            db.executescript('''
                CREATE TABLE IF NOT EXISTS sources (
                    key TEXT PRIMARY KEY, name TEXT, provider TEXT, board_url TEXT,
                    industry TEXT, country_coverage TEXT, permission_status TEXT,
                    last_checked TEXT, last_success TEXT, last_error TEXT,
                    raw_count INTEGER DEFAULT 0, status TEXT DEFAULT 'not_checked',
                    failures INTEGER DEFAULT 0, next_refresh TEXT, validators TEXT DEFAULT '{}'
                );
                CREATE TABLE IF NOT EXISTS records (
                    source_key TEXT NOT NULL REFERENCES sources(key), id TEXT NOT NULL,
                    payload TEXT NOT NULL, first_seen TEXT NOT NULL, last_seen TEXT NOT NULL,
                    status TEXT NOT NULL, PRIMARY KEY (source_key, id)
                );
                CREATE INDEX IF NOT EXISTS records_status ON records(status);
                CREATE TABLE IF NOT EXISTS runs (
                    id INTEGER PRIMARY KEY, source_key TEXT NOT NULL REFERENCES sources(key),
                    started_at TEXT, finished_at TEXT, status TEXT, raw_count INTEGER,
                    attempts INTEGER, error TEXT
                );
            ''')
            db.execute(f'PRAGMA user_version={SCHEMA_VERSION}')

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        try:
            with db:
                yield db
        finally:
            db.close()

    def register(self, sources):
        with self.connect() as db:
            for s in sources:
                category, _ = classify({}, s.get('sector'))
                db.execute('''INSERT INTO sources(key,name,provider,board_url,industry,country_coverage,permission_status)
                    VALUES(?,?,?,?,?,?,?) ON CONFLICT(key) DO UPDATE SET name=excluded.name,
                    provider=excluded.provider,board_url=excluded.board_url,industry=excluded.industry,
                    country_coverage=excluded.country_coverage,permission_status=excluded.permission_status''',
                    (source_key(s), s.get('name'), s.get('provider'), safe_url(s.get('url')),
                     category, json.dumps(s.get('country_coverage', ['unknown'])),
                     s.get('permission_status', 'local_api_review_required')))

    def refresh(self, sources, *, fetcher=None, retries=1, interval=3600, force=False, sleep=time.sleep):
        """Sequential source requests, bounded retries and persisted backoff.

        Failed/partial/capped requests never close records. Missing vacancies stay
        visible as unconfirmed for 30 days; explicit expiry can hide them sooner.
        """
        if not 0 <= retries <= 2 or not 60 <= interval <= 86400:
            raise ValueError('retries must be 0..2; interval must be 60..86400 seconds')
        self.register(sources)
        for s in sources:
            if not permitted(s):
                continue
            key, started = source_key(s), utcnow()
            with self.connect() as db:
                db.execute('BEGIN IMMEDIATE')
                row = db.execute('SELECT * FROM sources WHERE key=?', (key,)).fetchone()
                # Claim the source before the network call: simultaneous browser
                # and scheduled refreshes do not issue duplicate requests.
                if not force and row['next_refresh'] and row['next_refresh'] > started:
                    continue
                db.execute('UPDATE sources SET next_refresh=? WHERE key=?',
                           ((datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat(), key))
            attempts, error, found, validators, unchanged = 0, None, [], {}, False
            while attempts <= retries:
                attempts += 1
                try:
                    if fetcher is None and s.get('provider') in {'greenhouse', 'ashby', 'lever'}:
                        from .providers import fetch_snapshot
                        found, validators, unchanged = fetch_snapshot(s, json.loads(row['validators']))
                    else:
                        found = (fetcher or fetch_feed)(s)
                    if not isinstance(found, list) or len(found) > 50000:
                        raise ValueError('Unexpected or oversized source snapshot')
                    stamp = utcnow()
                    clean = [clean_record(item, s, stamp) for item in found]
                    error = None
                    break
                except Exception as exc:
                    # Never persist upstream error text: it may contain a key,
                    # credentialled URL, request headers or private search query.
                    error = 'Source refresh failed (' + type(exc).__name__ + '); check provider access, schema and limits'
                    if attempts <= retries:
                        sleep(min(2 ** attempts, 8))
            finished = utcnow()
            failures = row['failures'] + 1 if error else 0
            delay = min(86400, interval * 2 ** min(failures, 5))
            next_refresh = (datetime.now(timezone.utc) + timedelta(seconds=delay)).isoformat()
            with self.connect() as db:
                if not error:
                    if unchanged:
                        # HTTP 304 is a successful reconfirmation of the snapshot,
                        # but must not resurrect previously missing records.
                        db.execute("UPDATE records SET last_seen=? WHERE source_key=? AND status='seen'", (finished, key))
                    else:
                        db.execute("UPDATE records SET status='unconfirmed' WHERE source_key=?", (key,))
                        for job in clean:
                            db.execute('''INSERT INTO records VALUES(?,?,?,?,?,?)
                                ON CONFLICT(source_key,id) DO UPDATE SET payload=excluded.payload,
                                last_seen=excluded.last_seen,status=excluded.status''',
                                (key, job['id'], json.dumps(job), finished, finished, 'seen'))
                    count = row['raw_count'] if unchanged else len(clean)
                    db.execute('''UPDATE sources SET last_checked=?,last_success=?,last_error=NULL,
                        raw_count=?,status='ok',failures=0,next_refresh=?,validators=? WHERE key=?''',
                        (finished, finished, count, next_refresh, json.dumps(validators), key))
                else:
                    count = 0
                    db.execute('''UPDATE sources SET last_checked=?,last_error=?,status='error',
                        failures=?,next_refresh=? WHERE key=?''', (finished, error, failures, next_refresh, key))
                db.execute('INSERT INTO runs(source_key,started_at,finished_at,status,raw_count,attempts,error) VALUES(?,?,?,?,?,?,?)',
                           (key, started, finished, 'error' if error else 'not_modified' if unchanged else 'ok', count, attempts, error))
        return self.snapshot(sources)

    def snapshot(self, sources, *, now=None):
        self.register(sources)
        now = now or datetime.now(timezone.utc)
        threshold = (now - timedelta(days=30)).isoformat()
        jobs, health, errors = [], [], []
        with self.connect() as db:
            for s in sources:
                row = dict(db.execute('SELECT * FROM sources WHERE key=?', (source_key(s),)).fetchone())
                row['enabled'] = s.get('enabled', True) is not False
                row['permitted'] = permitted(s)
                row['status'] = row['status'] if row['permitted'] else 'disabled' if not row['enabled'] else 'permission_required'
                row['error'] = row.pop('last_error')
                row.pop('validators')
                row['live_count'] = 0
                row['uk_eligible_seen'] = 0
                provider = s.get('provider')
                if provider == 'smartrecruiters':
                    row['fetch_scope'] = f"bounded: {s.get('max_pages', 2)} list pages / {s.get('max_details', 25)} UK details"
                elif provider in {'reed', 'adzuna'}:
                    row['fetch_scope'] = 'bounded licensed search; not a full market snapshot'
                elif provider == 'website':
                    row['fetch_scope'] = f"bounded website: {s.get('max_details', 10)} details"
                else:
                    row['fetch_scope'] = 'single employer board response'
                if row['permitted']:
                    if row['error']:
                        errors.append(f"{s.get('name')}: {row['error']}")
                    for record in db.execute('SELECT * FROM records WHERE source_key=? AND last_seen>=?', (row['key'], threshold)):
                        job = json.loads(record['payload'])
                        expiry = job.get('expires_at')
                        if expiry and str(expiry)[:10] < now.date().isoformat():
                            continue
                        job.update(first_seen=record['first_seen'], last_seen=record['last_seen'],
                                   scan_status=record['status'] if row['status'] == 'ok' else 'source_unavailable')
                        job['source_references'] = [{'source': job['source'], 'source_key': row['key'], 'url': job['url'], 'id': job['id']}]
                        jobs.append(job)
                        if job['scan_status'] == 'seen':
                            row['live_count'] += 1
                            row['uk_eligible_seen'] += job.get('uk_eligibility') == 'confirmed_uk'
                health.append(row)
        return {'jobs': unique_jobs(jobs), 'source_health': health, 'errors': errors,
                'checked_at': max((r['last_checked'] or '' for r in health), default='') or None,
                'source_count': sum(r['permitted'] for r in health),
                'configured_source_count': len(sources),
                'sources_checked': sum(r['permitted'] and r['last_checked'] is not None for r in health),
                'sources_reached': sum(r['permitted'] and r['status'] == 'ok' for r in health),
                'sources_disabled': sum(not r['enabled'] for r in health),
                'sources_blocked': sum(r['enabled'] and not r['permitted'] for r in health)}


def permitted(source):
    if source.get('enabled', True) is False:
        return False
    status = source.get('permission_status', 'local_api_review_required')
    if status in {'denied', 'blocked', 'review_required'}:
        return False
    if source.get('provider') in {'reed', 'adzuna', 'website'}:
        return status in {'personal_use_reviewed', 'licensed', 'employer_permission'}
    return True
