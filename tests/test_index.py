"""Persistent refresh/index integration using synthetic records and real SQLite."""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from uk_hunter.index import VacancyIndex, source_key
from uk_hunter.webapp import scan_jobs
from uk_hunter.providers import fetch_snapshot

PROFILE = json.loads((Path(__file__).resolve().parents[1] / 'config/profile.example.json').read_text())
SOURCE = {'name': 'Example', 'provider': 'lever', 'board': 'example', 'sector': 'financial-services', 'url': 'https://jobs.lever.co/example'}


def job(identifier='1', **kw):
    return dict(id='lever:example:' + identifier, title='Research Scientist', company='Example', location='Remote',
                url='https://jobs.lever.co/example/' + identifier, date=None, description='Synthetic posting',
                salary_min=None, salary_max=None, source='lever', workplace_type='remote', **kw)


class IndexTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'vacancies.sqlite3'
        self.index = VacancyIndex(self.path)

    def tearDown(self):
        self.temp.cleanup()

    def test_persistence_and_broad_profile_independence(self):
        self.index.refresh([SOURCE], fetcher=lambda s: [job()], retries=0)
        snapshot = VacancyIndex(self.path).snapshot([SOURCE])
        self.assertEqual(len(snapshot['jobs']), 1)
        self.assertEqual(snapshot['jobs'][0]['uk_eligibility'], 'unknown')
        a = scan_jobs(PROFILE, [SOURCE], snapshot=snapshot)
        b = scan_jobs(dict(PROFILE, target_roles=['Research Scientist']), [SOURCE], snapshot=snapshot)
        self.assertEqual([j['id'] for j in a['jobs']], [j['id'] for j in b['jobs']])
        self.assertEqual(a['jobs'][0]['industry'], 'financial-services')
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)

    def test_failed_source_retains_jobs_and_does_not_store_exception_secret(self):
        self.index.refresh([SOURCE], fetcher=lambda s: [job()], retries=0)
        def fail(s):
            raise RuntimeError('https://provider.example/?api_key=DO_NOT_STORE_THIS')
        snapshot = self.index.refresh([SOURCE], fetcher=fail, force=True, retries=1, sleep=lambda n: None)
        self.assertEqual(len(snapshot['jobs']), 1)
        self.assertEqual(snapshot['jobs'][0]['scan_status'], 'source_unavailable')
        self.assertEqual(snapshot['source_health'][0]['live_count'], 0)
        self.assertEqual(snapshot['sources_reached'], 0)
        with self.index.connect() as db:
            run = db.execute('SELECT * FROM runs ORDER BY id DESC').fetchone()
            self.assertEqual(run['attempts'], 2)
        self.assertNotIn(b'DO_NOT_STORE_THIS', self.path.read_bytes())

    def test_missing_is_unconfirmed_not_closed_and_cautious_retention(self):
        self.index.refresh([SOURCE], fetcher=lambda s: [job()], retries=0)
        snapshot = self.index.refresh([SOURCE], fetcher=lambda s: [], force=True, retries=0)
        self.assertEqual(snapshot['jobs'][0]['scan_status'], 'unconfirmed')
        future = datetime.now(timezone.utc) + timedelta(days=31)
        self.assertEqual(self.index.snapshot([SOURCE], now=future)['jobs'], [])

    def test_explicit_expiry_and_future_posting_unknown_salary(self):
        expired = job('expired', expires_at='2000-01-01')
        self.index.refresh([SOURCE], fetcher=lambda s: [job(), expired], retries=0)
        jobs = self.index.snapshot([SOURCE])['jobs']
        self.assertEqual(len(jobs), 1)
        self.assertIsNone(jobs[0]['salary_min'])
        self.assertEqual(jobs[0]['salary_basis'], 'unknown')

    def test_bounded_retry_and_interval(self):
        calls = []
        def read(s):
            calls.append(1)
            return [job()]
        self.index.refresh([SOURCE], fetcher=read)
        self.index.refresh([SOURCE], fetcher=read)
        self.assertEqual(len(calls), 1)
        with self.index.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM runs').fetchone()[0], 1)

    def test_failure_isolation_and_disabled_permission_gates(self):
        bad = dict(SOURCE, board='bad', name='Bad')
        disabled = dict(SOURCE, board='disabled', enabled=False)
        website = {'name':'Website', 'provider':'website', 'url':'https://example.com/jobs'}
        def read(s):
            if s is bad:
                raise RuntimeError('offline')
            self.assertIs(s, SOURCE)
            return [job()]
        snapshot = self.index.refresh([SOURCE, bad, disabled, website], fetcher=read, retries=0)
        self.assertEqual(snapshot['sources_reached'], 1)
        self.assertEqual(snapshot['sources_disabled'], 1)
        self.assertEqual(snapshot['sources_blocked'], 1)
        self.assertEqual(len(snapshot['jobs']), 1)
        self.assertEqual(len(snapshot['source_health']), 4)

    def test_removed_sources_never_leak_back_into_browse(self):
        self.index.refresh([SOURCE], fetcher=lambda s: [job()])
        self.assertEqual(self.index.snapshot([])['jobs'], [])
        self.assertEqual(self.index.snapshot([dict(SOURCE, enabled=False)])['jobs'], [])

    def test_cross_provider_dedupe_keeps_provenance_and_distinct_requisitions(self):
        reed = {'name':'Reed', 'provider':'reed', 'permission_status':'personal_use_reviewed'}
        a, b = job('1'), job('2')
        a['location'] = b['location'] = 'London, UK'
        b['title'] = 'Senior Scientist'
        copy = dict(a, id='reed:1', source='reed', url='https://www.reed.co.uk/jobs/example/1')
        self.index.refresh([SOURCE, reed], fetcher=lambda s: [a,b] if s is SOURCE else [copy])
        jobs = self.index.snapshot([SOURCE, reed])['jobs']
        self.assertEqual(len(jobs), 2)
        self.assertTrue(any(any(r['source'] == 'reed' for r in j['source_references']) for j in jobs))

    def test_ambiguous_title_and_distinct_direct_requisitions_are_not_merged(self):
        from uk_hunter.dedupe import unique_jobs
        a, b = job('1'), job('2')
        copy = dict(a, id='reed:1', source='reed', url='https://www.reed.co.uk/jobs/example/1')
        self.assertEqual(len(unique_jobs([a,b,copy])), 3)
        other_ats = dict(a, id='greenhouse:example:3', source='greenhouse', url='https://example.com/jobs/3')
        self.assertEqual(len(unique_jobs([a,other_ats])), 2)
        exact = dict(a, id='reed:1', source='reed', url=a['url']+'?utm_source=example')
        merged = unique_jobs([a, exact])
        self.assertEqual(len(merged), 1)
        self.assertEqual(len(merged[0]['source_references']), 2)

    def test_allowlisted_metadata_and_credentials_not_persisted(self):
        unsafe = job()
        unsafe.update(api_key='SECRET_CONFIG_VALUE', raw={'token':'SECRET_CONFIG_VALUE'},
                      source_metadata={'api_key':'SECRET_CONFIG_VALUE','department':'Research'},
                      url='https://jobs.lever.co/example/1?api_key=SECRET_CONFIG_VALUE&gh_jid=1')
        self.index.refresh([dict(SOURCE, token='SECRET_CONFIG_VALUE')], fetcher=lambda s: [unsafe])
        self.assertNotIn(b'SECRET_CONFIG_VALUE', self.path.read_bytes())
        saved = self.index.snapshot([SOURCE])['jobs'][0]
        self.assertEqual(saved['source_metadata'], {'department':'Research'})
        self.assertIn('gh_jid=1', saved['url'])

    def test_malformed_snapshot_does_not_erase_previous_records(self):
        self.index.refresh([SOURCE], fetcher=lambda s: [job()])
        snapshot = self.index.refresh([SOURCE], fetcher=lambda s: [{'title':'broken'}], force=True, retries=0)
        self.assertEqual(len(snapshot['jobs']), 1)
        self.assertEqual(snapshot['source_health'][0]['status'], 'error')

    def test_newer_schema_is_rejected(self):
        with self.index.connect() as db:
            db.execute('PRAGMA user_version=999')
        with self.assertRaises(ValueError):
            VacancyIndex(self.path)

    def test_304_is_success_and_reconfirms_only_seen(self):
        self.index.refresh([SOURCE], fetcher=lambda s: [job('1'),job('2')])
        self.index.refresh([SOURCE], fetcher=lambda s: [job('1')], force=True)
        with patch('uk_hunter.providers.fetch_snapshot', return_value=([], {'etag':'x'}, True)):
            snapshot = self.index.refresh([SOURCE], force=True)
        self.assertEqual({j['scan_status'] for j in snapshot['jobs']}, {'seen','unconfirmed'})
        self.assertEqual(snapshot['sources_reached'], 1)

    def test_conditional_request_304_and_no_redirect(self):
        with patch('urllib.request.build_opener') as opener:
            opener.return_value.open.side_effect = HTTPError('https://api.lever.co',304,'',{},None)
            jobs, validators, unchanged = fetch_snapshot(SOURCE, {'etag':'"abc"'})
            self.assertTrue(unchanged)
            request = opener.return_value.open.call_args[0][0]
            self.assertEqual(request.get_header('If-none-match'), '"abc"')


if __name__ == '__main__':
    unittest.main()

class IndexedHTTPTests(unittest.TestCase):
    def test_browse_survives_restart_without_network_and_export_stays_local(self):
        from http.client import HTTPConnection
        import threading
        from uk_hunter import webapp
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            index = VacancyIndex(path / 'index.sqlite3')
            index.refresh([SOURCE], fetcher=lambda s: [job()])
            tracker = webapp.Tracker(path / 'tracker.json')
            with patch.object(webapp, 'read_sources', return_value=[SOURCE]), patch.object(webapp, 'read_profile', return_value=PROFILE), patch('uk_hunter.providers.fetch_snapshot', side_effect=AssertionError('browse must not fetch')):
                for _ in range(2):
                    server = webapp.App(('127.0.0.1',0), tracker=tracker, index_path=path / 'index.sqlite3')
                    thread = threading.Thread(target=server.serve_forever, daemon=True)
                    thread.start()
                    try:
                        connection = HTTPConnection(*server.server_address, timeout=5)
                        connection.request('GET', '/api/jobs')
                        response = connection.getresponse()
                        report = json.loads(response.read())
                        self.assertEqual(response.status, 200)
                        self.assertTrue(report['indexed'])
                        self.assertEqual(len(report['jobs']), 1)
                        connection.request('GET', '/api/export')
                        response = connection.getresponse()
                        self.assertEqual(json.loads(response.read())['tracker'], {})
                        connection.close()
                    finally:
                        server.shutdown()
                        server.server_close()

    def test_refresh_requires_json_same_origin_and_ignores_arbitrary_url(self):
        from http.client import HTTPConnection
        import threading
        from uk_hunter import webapp
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            server = webapp.App(('127.0.0.1',0), tracker=webapp.Tracker(path / 'tracker.json'), index_path=path / 'index.sqlite3')
            threading.Thread(target=server.serve_forever, daemon=True).start()
            try:
                connection = HTTPConnection(*server.server_address, timeout=5)
                connection.request('POST','/api/refresh', '{}', {'Content-Type':'application/json','Origin':'https://evil.example'})
                response = connection.getresponse()
                self.assertEqual(response.status,403)
                response.read()
                self.assertFalse((path / 'index.sqlite3').exists())
                with patch.object(webapp, 'read_sources', return_value=[]), patch.object(webapp, 'read_profile', return_value=PROFILE), patch('uk_hunter.providers.fetch_snapshot', side_effect=AssertionError('no configured sources')):
                    connection.request('POST','/api/refresh', json.dumps({'url':'http://127.0.0.1/private'}), {'Content-Type':'application/json'})
                    response = connection.getresponse()
                    self.assertEqual(response.status,200)
                    self.assertEqual(json.loads(response.read())['jobs'], [])
                connection.close()
            finally:
                server.shutdown()
                server.server_close()
