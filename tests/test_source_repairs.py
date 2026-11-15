"""Transport, bounded discovery and persistence regressions using fictional jobs."""
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from uk_hunter.providers import read_ats_json, fetch_snapshot, fetch_feed
from uk_hunter.source_health import FeedResult, SourceError
from uk_hunter.greenhouse_details import fetch_greenhouse_details
from uk_hunter.workable import fetch_workable
from uk_hunter.index import VacancyIndex, source_key
from uk_hunter.evaluate import evaluate
from uk_hunter.webapp import scan_jobs, parse_employer_url

ROOT = Path(__file__).resolve().parents[1]
SOURCE = {'name': 'Example Defence', 'provider': 'greenhouse', 'board': 'example',
          'url': 'https://job-boards.greenhouse.io/example', 'fetch_strategy': 'uk_metadata_details'}
PROFILE = json.loads((ROOT / 'config/profile.example.json').read_text())


def posting(identifier=1, location='Example, United Kingdom', **values):
    return dict(id=identifier, title='Risk Manager', location={'name': location},
                absolute_url=f'https://job-boards.greenhouse.io/example/jobs/{identifier}', **values)


def reader_for(items, *, failure=None):
    calls = []
    def read(url, **kwargs):
        calls.append((url, kwargs))
        if url.endswith('/jobs'):
            return {'jobs': items}, {}, False, 100
        if failure:
            raise failure
        identifier = int(url.rsplit('/', 1)[-1])
        return posting(identifier, content='Synthetic essential requirements.'), {}, False, 50
    return read, calls


class Response:
    def __init__(self, url, raw=b'{}', final=None):
        self.url, self.raw, self.final = url, raw, final
        self.headers = {'ETag': '"fixture"'}
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def geturl(self):
        return self.final or self.url
    def read(self, cap):
        return self.raw[:cap]


class TransportTests(unittest.TestCase):
    url = 'https://boards-api.greenhouse.io/v1/boards/example/jobs'

    def test_http_categories_do_not_leak_body_url_or_headers(self):
        for status, category, retryable in [(404, 'http_not_found', False), (403, 'access_denied', False),
                                             (429, 'rate_limited', True), (503, 'provider_error', True),
                                             (302, 'redirect_rejected', False)]:
            with self.subTest(status=status), patch('urllib.request.build_opener') as opener:
                opener.return_value.open.side_effect = HTTPError('https://secret/?key=PRIVATE', status, 'PRIVATE', {'Retry-After': '120'}, io.BytesIO(b'PRIVATE'))
                with self.assertRaises(SourceError) as caught:
                    read_ats_json(self.url)
                self.assertEqual(caught.exception.category, category)
                self.assertEqual(caught.exception.http_status, status)
                self.assertEqual(caught.exception.retryable, retryable)
                self.assertNotIn('PRIVATE', str(caught.exception))

    def test_get_limits_invalid_json_and_redirects(self):
        for raw, final, category in [(b'x' * 101, None, 'response_too_large'),
                                     (b'not json', None, 'invalid_json'),
                                     (b'{}', 'https://evil.example', 'redirect_rejected')]:
            with self.subTest(category=category), patch('urllib.request.build_opener') as opener:
                opener.return_value.open.return_value = Response(self.url, raw, final)
                with self.assertRaises(SourceError) as caught:
                    read_ats_json(self.url, max_bytes=100)
                self.assertEqual(caught.exception.category, category)
                self.assertEqual(opener.return_value.open.call_args[0][0].get_method(), 'GET')

    def test_network_failure_categories(self):
        for error, category in [(TimeoutError('PRIVATE'), 'network_timeout'),
                                (URLError(TimeoutError('PRIVATE')), 'network_timeout'),
                                (URLError('PRIVATE'), 'network_error')]:
            with patch('urllib.request.build_opener') as opener:
                opener.return_value.open.side_effect = error
                with self.assertRaises(SourceError) as caught:
                    read_ats_json(self.url)
                self.assertEqual(str(caught.exception), category)

    def test_single_response_greenhouse_still_uses_full_content(self):
        url = self.url + '?content=true'
        with patch('urllib.request.build_opener') as opener:
            opener.return_value.open.return_value = Response(url, json.dumps({'jobs': [posting(content='Synthetic')]}).encode())
            jobs, validators, unchanged = fetch_snapshot(dict(SOURCE, fetch_strategy=None))
            self.assertEqual(jobs[0]['description'], 'Synthetic')
            self.assertFalse(unchanged)
            self.assertEqual(validators['etag'], '"fixture"')
            self.assertEqual(opener.return_value.open.call_args[0][0].full_url, url)


class GreenhouseDetailsTests(unittest.TestCase):
    def test_uk_and_ambiguous_visible_overseas_excluded_no_advert_url_fetch(self):
        read, calls = reader_for([posting(1), posting(2, 'Remote'), posting(3, 'Paris, France')])
        result = fetch_greenhouse_details(SOURCE, reader=read, sleep=lambda n: None)
        self.assertEqual(len(result), 2)
        self.assertTrue(result.report['complete'])
        self.assertEqual(result.report['list_count'], 3)
        self.assertEqual(result[0]['country'], 'GB')
        self.assertNotIn('country', result[1])
        self.assertTrue(all(url.startswith('https://boards-api.greenhouse.io/v1/boards/example/jobs') for url, _ in calls))
        self.assertTrue(all('content=true' not in url for url, _ in calls))

    def test_detail_cap_retains_metadata_and_reports_partial(self):
        read, calls = reader_for([posting(1), posting(2), posting(3, 'Remote')])
        result = fetch_greenhouse_details(dict(SOURCE, max_details=1), reader=read, sleep=lambda n: None)
        self.assertEqual(len(result), 3)
        self.assertEqual(len(calls), 2)
        self.assertFalse(result.report['complete'])
        self.assertEqual(result.report['details_pending'], 2)
        self.assertEqual(result[1]['detail_status'], 'metadata_only')

    def test_detail_failure_keeps_metadata_and_stops_on_rate_limit(self):
        read, calls = reader_for([posting(1), posting(2)], failure=SourceError('rate_limited', http_status=429))
        result = fetch_greenhouse_details(SOURCE, reader=read, sleep=lambda n: None)
        self.assertEqual(len(result), 2)
        self.assertEqual(len(calls), 2)
        self.assertEqual(result[0]['detail_status'], 'unavailable')
        self.assertEqual(result.report['details_failed'], 1)
        self.assertEqual(result.report['detail_error_category'], 'rate_limited')
        self.assertEqual(result.report['detail_http_status'], 429)

    def test_unsafe_ids_schema_and_budgets_are_rejected(self):
        for items in [[posting('../secret')], [posting(True)], [None]]:
            read, _ = reader_for(items)
            with self.assertRaises(SourceError):
                fetch_greenhouse_details(SOURCE, reader=read)
        for options in [{'max_details': 51}, {'max_seconds': 0}, {'max_total_bytes': True}, {'board': '../secret'}]:
            with self.assertRaises(ValueError):
                fetch_greenhouse_details(dict(SOURCE, **options))

    def test_empty_board_is_complete(self):
        read, calls = reader_for([])
        result = fetch_greenhouse_details(SOURCE, reader=read)
        self.assertEqual(result, [])
        self.assertTrue(result.report['complete'])
        self.assertEqual(len(calls), 1)

    def test_time_and_total_byte_caps_leave_discoverable_metadata(self):
        read, calls = reader_for([posting(1)])
        result = fetch_greenhouse_details(dict(SOURCE, max_seconds=1), reader=read, clock=iter([0, 2]).__next__)
        self.assertEqual(len(calls), 1)
        self.assertFalse(result.report['complete'])
        # A consumed list budget prevents further detail requests.
        def full_list(url, **kw):
            self.assertTrue(url.endswith('/jobs'))
            return {'jobs': [posting()]}, {}, False, 1000
        result = fetch_greenhouse_details(dict(SOURCE, max_total_bytes=1000), reader=full_list)
        self.assertFalse(result.report['complete'])
        self.assertEqual(len(result), 1)

    def test_metadata_strategy_does_not_use_conditional_list_cache(self):
        with patch('uk_hunter.greenhouse_details.fetch_greenhouse_details', return_value=FeedResult([], complete=False)) as fetch:
            jobs, validators, unchanged = fetch_snapshot(SOURCE, {'etag': 'old'})
        self.assertEqual(validators, {})
        self.assertFalse(unchanged)
        self.assertNotIn('validators', fetch.call_args.kwargs)

    def test_new_south_wales_is_not_uk_but_mixed_uk_postings_remain(self):
        from uk_hunter.uk_scope import obviously_non_uk
        self.assertTrue(obviously_non_uk('Sydney, New South Wales, Australia'))
        self.assertTrue(obviously_non_uk('New England, United States'))
        self.assertFalse(obviously_non_uk('Sydney, New South Wales, Australia; London, UK'))
        read, _ = reader_for([posting(1, 'Sydney, New South Wales, Australia'), posting(2, 'Cardiff, Wales')])
        result = fetch_greenhouse_details(dict(SOURCE, max_details=0), reader=read)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['country'], 'GB')


class WorkableTests(unittest.TestCase):
    source = {'name': 'Example Bank', 'board': 'example-bank', 'provider': 'workable'}

    def item(self, **overrides):
        return dict(title='Risk Manager', shortcode='ABC123', url='https://apply.workable.com/j/ABC123',
                    published_on='2026-11-01', created_at='2020-01-01', description='<p>Synthetic</p>', **overrides)

    def fetch(self, items):
        def read(url, **kwargs):
            self.assertEqual(url, 'https://apply.workable.com/api/v1/widget/accounts/example-bank?details=true')
            return {'jobs': items}, {}, False, 100
        return fetch_workable(self.source, reader=read)

    def test_multiple_countries_prefer_explicit_uk_and_keep_unknown_pay_and_workplace(self):
        result = self.fetch([self.item(locations=[{'city': 'Paris', 'countryCode': 'FR', 'country': 'France'},
                                                  {'city': 'Example', 'countryCode': 'GB', 'country': 'United Kingdom'}], telecommuting=False)])
        job = result[0]
        self.assertEqual(job['country'], 'GB')
        self.assertEqual(job['id'], 'workable:example-bank:ABC123')
        self.assertEqual(job['date'], '2026-11-01')
        self.assertEqual(job['workplace_type'], 'unknown')
        self.assertIsNone(job['salary_min'])
        self.assertEqual(job['description'], 'Synthetic')

    def test_remote_without_country_does_not_imply_uk(self):
        job = self.fetch([self.item(telecommuting=True)])[0]
        self.assertIsNone(job['country'])
        self.assertEqual(job['workplace_type'], 'remote')

    def test_empty_and_malformed_responses(self):
        self.assertEqual(self.fetch([]), [])
        for obj in [{'jobs': None}, {'jobs': [None]}, {'jobs': [self.item(locations='invalid')]}]:
            with self.assertRaises(SourceError):
                fetch_workable(self.source, reader=lambda *a, **kw: (obj, {}, False, 100))

    def test_repeated_shortcode_combines_locations_without_inflating_count(self):
        result = self.fetch([self.item(locations=[{'city':'Paris','country':'France','countryCode':'FR'}]),
                             self.item(locations=[{'city':'Example','country':'United Kingdom','countryCode':'GB'}])])
        self.assertEqual(len(result), 1)
        self.assertEqual(result.report['list_count'], 2)
        self.assertEqual(result[0]['country'], 'GB')
        self.assertIn('Paris', result[0]['location'])
        self.assertIn('Example', result[0]['location'])

    def test_explicit_overseas_workable_country_is_not_uk_in_discovery(self):
        jobs = self.fetch([self.item(locations=[{'city':'Example','countryCode':'US'}])])
        report = scan_jobs(PROFILE, [self.source], fetcher=lambda s: jobs)
        self.assertEqual(report['jobs'], [])

    def test_validated_board_and_employer_url(self):
        for board in ['../private', 'example?key=secret', '', 'https://evil.example']:
            with self.assertRaises(ValueError):
                fetch_workable(dict(self.source, board=board))
        parsed = parse_employer_url('https://apply.workable.com/example-bank/', 'Example')
        self.assertEqual((parsed['provider'], parsed['board']), ('workable', 'example-bank'))
        for url in ['https://apply.workable.com/j/ABC123', 'https://apply.workable.com/api/accounts/foo']:
            with self.assertRaises(ValueError):
                parse_employer_url(url, 'Example')

    def test_source_registry_routes_replacements(self):
        sources = {s['name']: s for s in json.loads((ROOT / 'config/sources.json').read_text())['sources']}
        self.assertEqual(sources['Multiverse']['provider'], 'ashby')
        self.assertEqual(sources['Multiverse']['board'], 'multiverse')
        self.assertEqual(sources['Starling Bank']['provider'], 'workable')
        self.assertEqual(sources['Anduril Industries']['fetch_strategy'], 'uk_metadata_details')
        with patch('uk_hunter.workable.fetch_workable', return_value=[]) as fetch:
            fetch_feed(self.source)
        fetch.assert_called_once()


class PersistenceTests(unittest.TestCase):
    def test_cli_json_and_browser_direct_scan_keep_partial_coverage(self):
        from contextlib import redirect_stdout
        from uk_hunter.cli import main
        read, _ = reader_for([posting()])
        jobs = fetch_greenhouse_details(dict(SOURCE, max_details=0), reader=read)
        with tempfile.TemporaryDirectory() as folder:
            config = Path(folder) / 'sources.json'
            config.write_text(json.dumps({'sources': [SOURCE]}))
            stdout = io.StringIO()
            with patch('uk_hunter.cli.fetch_feed', return_value=jobs), redirect_stdout(stdout):
                result = main(['search', '--all', '--sources', str(config), '--format', 'json'])
            report = json.loads(stdout.getvalue())
            self.assertEqual(result, 0)
            self.assertEqual(report['source_health'][0]['status'], 'partial')
            self.assertTrue(report['errors'])
            self.assertEqual(len(report['results']), 1)
        report = scan_jobs(PROFILE, [SOURCE], fetcher=lambda s: jobs)
        self.assertEqual(report['source_health'][0]['status'], 'partial')
        self.assertEqual(report['sources_partial'], 1)

    def test_partial_scan_preserves_unseen_records_stale_details_and_last_full_success(self):
        read, _ = reader_for([posting(1), posting(2)])
        complete = fetch_greenhouse_details(SOURCE, reader=read, sleep=lambda n: None)
        partial = FeedResult([dict(complete[0], description='', detail_status='metadata_only')], complete=False,
                             list_count=1, details_attempted=0, details_succeeded=0, details_pending=1)
        with tempfile.TemporaryDirectory() as folder:
            index = VacancyIndex(Path(folder) / 'index.sqlite3')
            original = index.refresh([SOURCE], fetcher=lambda s: complete)
            checked = original['source_health'][0]['last_success']
            snapshot = index.refresh([SOURCE], fetcher=lambda s: partial, force=True)
            self.assertEqual(snapshot['source_health'][0]['status'], 'partial')
            self.assertEqual(snapshot['source_health'][0]['last_success'], checked)
            self.assertEqual(snapshot['source_health'][0]['live_count'], 1)
            self.assertEqual(len(snapshot['jobs']), 2)
            job = next(j for j in snapshot['jobs'] if j['id'].endswith(':1'))
            self.assertEqual(job['detail_status'], 'stale')
            self.assertEqual(job['description'], complete[0]['description'])
            self.assertIsNotNone(job['detail_last_success'])
            self.assertEqual({j['scan_status'] for j in snapshot['jobs']}, {'seen', 'source_partial'})
            with index.connect() as db:
                self.assertEqual({r['status'] for r in db.execute('SELECT status FROM records')}, {'seen'})
            # The saved index remains equally honest after restart and in API output.
            report = scan_jobs(PROFILE, [SOURCE], snapshot=VacancyIndex(index.path).snapshot([SOURCE]))
            self.assertEqual(report['source_health'][0]['status'], 'partial')

    def test_missing_details_prevent_shortlist_even_when_title_location_pay_pass(self):
        profile = dict(PROFILE, target_roles=['risk manager'], nearby_places=['Example'])
        read, _ = reader_for([posting()])
        job = fetch_greenhouse_details(dict(SOURCE, max_details=0), reader=read)[0]
        self.assertEqual(evaluate(job, profile)['verdict'], 'REVIEW')

    def test_source_strategy_and_each_budget_is_part_of_snapshot_identity(self):
        for key, value in [('fetch_strategy', 'full'), ('max_seconds', 45), ('max_total_bytes', 10000000), ('max_details', 1)]:
            self.assertNotEqual(source_key(SOURCE), source_key(dict(SOURCE, **{key: value})))

    def test_retry_only_transient_errors_and_redact_every_public_path(self):
        with tempfile.TemporaryDirectory() as folder:
            index = VacancyIndex(Path(folder) / 'index.sqlite3')
            for category, attempts in [('http_not_found', 1), ('response_too_large', 1), ('rate_limited', 2)]:
                sleeps = []
                def fail(s):
                    raise SourceError(category, http_status=429 if category == 'rate_limited' else 404, retry_after=3)
                report = index.refresh([SOURCE], fetcher=fail, force=True, sleep=sleeps.append)
                self.assertEqual(report['source_health'][0]['error_category'], category)
                with index.connect() as db:
                    self.assertEqual(db.execute('SELECT attempts FROM runs ORDER BY id DESC').fetchone()[0], attempts)
                self.assertEqual(len(sleeps), attempts - 1)
            def private_failure(s):
                raise RuntimeError('PRIVATE_QUERY https://example.com/?key=PRIVATE_KEY')
            report = scan_jobs(PROFILE, [SOURCE], fetcher=private_failure)
            self.assertNotIn('PRIVATE_', json.dumps(report))
            index.refresh([SOURCE], fetcher=private_failure, force=True)
            self.assertNotIn(b'PRIVATE_', index.path.read_bytes())

    def test_long_retry_after_defers_instead_of_retrying_early(self):
        with tempfile.TemporaryDirectory() as folder:
            index = VacancyIndex(Path(folder) / 'index.sqlite3')
            sleeps = []
            def fail(s):
                raise SourceError('rate_limited', retry_after=120)
            index.refresh([SOURCE], fetcher=fail, interval=60, retries=2, sleep=sleeps.append)
            self.assertEqual(sleeps, [])
            with index.connect() as db:
                self.assertEqual(db.execute('SELECT attempts FROM runs').fetchone()[0], 1)

    def test_v1_database_migration_preserves_jobs(self):
        read, _ = reader_for([posting()])
        jobs = fetch_greenhouse_details(SOURCE, reader=read, sleep=lambda n: None)
        with tempfile.TemporaryDirectory() as folder:
            index = VacancyIndex(Path(folder) / 'index.sqlite3')
            index.refresh([SOURCE], fetcher=lambda s: jobs)
            with index.connect() as db:
                db.execute('ALTER TABLE sources DROP COLUMN diagnostics')
                db.execute('ALTER TABLE runs DROP COLUMN diagnostics')
                db.execute('PRAGMA user_version=1')
            reopened = VacancyIndex(index.path)
            self.assertEqual(len(reopened.snapshot([SOURCE])['jobs']), 1)
            with reopened.connect() as db:
                self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0], 2)


if __name__ == '__main__':
    unittest.main()
