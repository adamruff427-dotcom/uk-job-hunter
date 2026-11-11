"""Search Everything is opt-in explicit, broad across configured sources, and profile-independent for visibility."""
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
from unittest.mock import patch
import unittest

from uk_hunter import cli, webapp

ROOT = Path(__file__).resolve().parents[1]


def sample(job_id, title, description='', location='London, UK'):
    return {
        'id': f'lever:example:{job_id}', 'title': title, 'company': 'Example',
        'location': location, 'url': f'https://jobs.lever.co/example/{job_id}',
        'date': None, 'description': description, 'workplace_type': 'hybrid',
        'salary_min': 45000, 'salary_max': 60000, 'source': 'lever',
    }


class BroadSearchTests(unittest.TestCase):
    def test_public_browser_has_explicit_broad_search_default(self):
        html = (ROOT / 'uk_hunter/static/index.html').read_text()
        js = (ROOT / 'uk_hunter/static/app.js').read_text()
        self.assertIn('id="searchAllBtn"', html)
        self.assertIn('id="searchMatchesBtn"', html)
        self.assertIn('Search everything', html)
        self.assertIn('Search for me', html)
        self.assertIn("scope: 'all'", js)
        self.assertIn("setScope(scope, {resetText:true})", js)
        self.assertIn('job.description', js)
        self.assertIn('all configured sources', html)
        self.assertIn('Load more jobs', js)
        self.assertIn('state.renderLimit += 60', js)

    def test_unmatched_jobs_remain_visible_in_broad_scan(self):
        profile = json.loads((ROOT / 'config/profile.example.json').read_text())
        sources = [{'name':'Bank','sector':'financial-services'}, {'name':'Laboratory','sector':'healthcare'}]
        def fake_fetch(src):
            return [sample(src['name'].lower(), 'Specialist Laboratory Researcher' if src['name']=='Laboratory' else 'Operations Manager')]
        result = webapp.scan_jobs(profile, sources, fetcher=fake_fetch)
        self.assertEqual(result['source_count'],2)
        self.assertEqual(result['sources_reached'],2)
        self.assertEqual(len(result['jobs']),2)
        self.assertIn('REJECT', {j['verdict'] for j in result['jobs']})
        self.assertEqual(sum(x['count'] for x in result['industries']),2)

    def test_cli_all_includes_jobs_outside_profile(self):
        jobs=[sample('good','Operations Manager'),sample('other','Research Scientist')]
        with patch.object(cli, 'fetch_feed', return_value=jobs), redirect_stdout(StringIO()) as output:
            status=cli.main(['search', '--all', '--format','json', '--limit','250'])
        self.assertEqual(status,0)
        report=json.loads(output.getvalue())
        self.assertEqual(len(report['results']),2)
        self.assertEqual({r['title'] for r in report['results']}, {'Operations Manager','Research Scientist'})
        self.assertIn('reject', {r['fit'] for r in report['results']})

    def test_cli_personal_mode_remains_narrow(self):
        jobs=[sample('good','Operations Manager'),sample('other','Research Scientist')]
        with patch.object(cli,'fetch_feed',return_value=jobs), redirect_stdout(StringIO()) as output:
            status=cli.main(['search','--format','json'])
        self.assertEqual(status,0)
        report=json.loads(output.getvalue())
        self.assertNotIn('Research Scientist', [r['title'] for r in report['results']])

    def test_cli_broad_keyword_search_in_description(self):
        jobs=[sample('hello','Finance Analyst','We use quantum simulations.'),
              sample('world','Risk Manager','Process improvement only.')]
        with patch.object(cli,'fetch_feed',return_value=jobs), redirect_stdout(StringIO()) as output:
            status=cli.main(['search','--all','--query','quantum','--format','json'])
        self.assertEqual(status,0)
        report=json.loads(output.getvalue())
        self.assertEqual([r['title'] for r in report['results']], ['Finance Analyst'])

if __name__ == '__main__':
    unittest.main()
