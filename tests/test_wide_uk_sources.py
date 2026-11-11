"""Wide UK search regressions: credential handling, paging, source failure and discovery."""
from __future__ import annotations

import json
from pathlib import Path
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from uk_hunter.extra_providers import fetch_reed, fetch_adzuna, reed_job
from uk_hunter.dedupe import unique_jobs
from uk_hunter.webapp import scan_jobs

ROOT = Path(__file__).resolve().parents[1]
PROFILE = json.loads((ROOT / 'config/profile.example.json').read_text())


class ReedTests(unittest.TestCase):
    def test_reed_does_not_run_without_credentials(self):
        with self.assertRaisesRegex(RuntimeError, 'REED_API_KEY'):
            fetch_reed({'queries':['']}, environ={})

    def test_reed_broad_search_paginates_without_keywords(self):
        called=[]
        def reader(url, key):
            self.assertEqual(key,'fake-secret')
            called.append(url)
            params=parse_qs(urlsplit(url).query)
            self.assertNotIn('keywords',params)
            offset=int(params['resultsToSkip'][0])
            rows=[{'jobId':101+offset+i, 'jobTitle':'Operations Manager',
                   'employerName':'Example Co', 'locationName':'Leeds',
                   'jobUrl':f'https://www.reed.co.uk/jobs/operations-manager/{101+offset+i}',
                   'minimumSalary':500} for i in range(2 if offset == 0 else 1)]
            return {'results':rows}
        result=fetch_reed({'queries':[''], 'max_pages':2,'results_per_page':2},reader=reader,environ={'REED_API_KEY':'fake-secret'})
        self.assertEqual(len(result),3)
        self.assertEqual(len(called),2)
        self.assertTrue(all(j['salary_min'] is None for j in result))
        self.assertTrue(all(j['source']=='reed' for j in result))

    def test_reed_rejects_bad_limits(self):
        with self.assertRaises(ValueError):
            fetch_reed({'queries':[''], 'max_pages':500},environ={'REED_API_KEY':'token'})

    def test_reed_errors_never_leak_key(self):
        def bad_reader(url,key):
            raise Exception('Authorization: Basic '+key)
        with self.assertRaises(RuntimeError) as ctx:
            fetch_reed({'queries':['risk']},reader=bad_reader,environ={'REED_API_KEY':'super-secret'})
        self.assertNotIn('super-secret',str(ctx.exception))

    def test_reed_accepts_https_link_only(self):
        j=reed_job({'jobId':13,'jobTitle':'Risk Manager','jobUrl':'http://localhost/jobs/13'})
        self.assertTrue(j['url'].startswith('https://www.reed.co.uk/jobs/risk-manager/'))

class AdzunaWideTests(unittest.TestCase):
    def test_adzuna_uses_broad_recent_search_and_pages(self):
        called=[]
        def reader(url):
            called.append(url)
            params=parse_qs(urlsplit(url).query)
            self.assertNotIn('what',params)
            self.assertEqual(params['sort_by'],['date'])
            number=int(urlsplit(url).path.rsplit('/',1)[-1])
            count=2 if number == 1 else 1
            return {'results':[{'id':f'{number}-{i}','title':'Manager',
                                 'redirect_url':f'https://www.adzuna.co.uk/jobs/details/{number}-{i}',
                                 'company':{'display_name':'Example'},
                                 'salary_min':75000} for i in range(count)]}
        data=fetch_adzuna({'queries':[''],'max_pages':2,'results_per_page':2},reader=reader,
                          environ={'ADZUNA_APP_ID':'abc','ADZUNA_APP_KEY':'token'})
        self.assertEqual(len(data),3)
        self.assertEqual(len(called),2)
        self.assertTrue(all(j['salary_min'] is None for j in data))

    def test_adzuna_limit_is_bounded(self):
        with self.assertRaises(ValueError):
            fetch_adzuna({'queries':[''],'results_per_page':2000},
                         environ={'ADZUNA_APP_ID':'x','ADZUNA_APP_KEY':'y'})

class CoverageTests(unittest.TestCase):
    def test_registry_has_verified_additions_and_diversity(self):
        sources=json.loads((ROOT/'config/sources.json').read_text())['sources']
        self.assertGreaterEqual(len(sources),40)
        self.assertIn('Nucleus Global',{s['name'] for s in sources})
        self.assertGreaterEqual(len({s['sector'] for s in sources}),10)

    def test_disabled_sources_never_queried(self):
        called=[]
        def fetch(s):
            called.append(s['name'])
            return []
        outcome=scan_jobs(PROFILE,[{'name':'Disabled','enabled':False},{'name':'Active'}],fetcher=fetch)
        self.assertEqual(called,['Active'])
        self.assertEqual(outcome['sources_disabled'],1)
        self.assertEqual(outcome['source_count'],1)
        self.assertEqual(outcome['sources_reached'],1)
        self.assertEqual(outcome['source_health'][0]['status'],'ok')

    def test_source_failure_does_not_masquerade_as_no_jobs(self):
        def fetch(source):
            if source['name']=='Broken': raise RuntimeError('HTTP 403')
            return []
        result=scan_jobs(PROFILE,[{'name':'Broken','provider':'reed'},
                                      {'name':'Good','provider':'greenhouse'}],fetcher=fetch)
        self.assertEqual(len(result['source_health']),2)
        self.assertEqual(result['sources_reached'],1)
        self.assertEqual(result['errors'][0],'Broken: HTTP 403')
        self.assertEqual([r['status'] for r in result['source_health']],['error','ok'])

    def test_direct_employer_beats_reed_copy(self):
        a={'id':'reed:1','source':'reed','company':'Example','title':'Risk Manager',
           'location':'London, UK','url':'https://www.reed.co.uk/jobs/risk-manager/1'}
        b={**a,'id':'greenhouse:1','source':'greenhouse',
           'url':'https://job-boards.greenhouse.io/example/jobs/1'}
        result = unique_jobs([a,b])
        self.assertEqual(result[0]['id'], b['id'])
        self.assertEqual({r['source'] for r in result[0]['source_references']}, {'reed', 'greenhouse'})

if __name__ == '__main__':
    unittest.main()
