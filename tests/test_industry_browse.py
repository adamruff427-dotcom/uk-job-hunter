"""Industry browsing: correct sector for employer, not role; UK source hygiene."""
import json
import unittest
from pathlib import Path

from uk_hunter.industries import INDUSTRIES, LABELS, classify, industry_counts
from uk_hunter.uk_scope import obviously_non_uk
from uk_hunter.webapp import ROOT, scan_jobs, parse_employer_url

PROFILE = json.loads((ROOT / 'config/profile.example.json').read_text())


def job(job_id, title, company='Employer', location='Leeds, UK'):
    return {'id': job_id, 'title': title, 'company': company, 'location': location,
            'workplace_type': 'hybrid', 'date': None,
            'url': 'https://example.org/jobs/' + job_id, 'description': '',
            'salary_min': None, 'salary_max': None, 'source':'ashby'}


class IndustryClassificationTests(unittest.TestCase):
    def test_canonical_list_has_no_duplicate_ids(self):
        self.assertEqual(len(INDUSTRIES), len(set(LABELS)))
        self.assertIn('unclassified', LABELS)

    def test_role_does_not_override_employer_sector(self):
        sector, basis = classify(job('one','Security Operations Manager'), 'banking')
        self.assertEqual((sector,basis), ('financial-services','employer'))
        sector, basis = classify(job('two','Finance Analyst'), 'energy')
        self.assertEqual((sector,basis), ('energy-utilities','employer'))

    def test_known_employer_sectors(self):
        for raw, expected in [('financial technology','financial-services'),
                              ('defence technology','defence-security'),
                              ('consultancy','professional-services'),
                              ('saas','technology'),
                              ('retail','retail-consumer')]:
            with self.subTest(sector=raw):
                self.assertEqual(classify(job('id','Test Role'),raw)[0], expected)

    def test_unknown_is_not_falsely_classified_by_role(self):
        self.assertEqual(classify(job('one','Banking Compliance Manager')), ('unclassified','unknown'))

    def test_curated_source_wins_over_ambiguous_job_metadata(self):
        sector, basis = classify({**job('one','Software Engineer'), 'industry':'Technology'}, 'banking')
        self.assertEqual((sector,basis), ('financial-services','employer'))

    def test_explicit_industry_beats_aggregator_source(self):
        result = classify({**job('one','Risk Manager'), 'industry':'healthcare'}, 'multi-sector')
        self.assertEqual(result, ('healthcare','posting'))

    def test_strong_posting_clue_when_no_source(self):
        obj = {**job('one','Business Partner'), 'description':'We are an NHS Foundation Trust providing local services.'}
        self.assertEqual(classify(obj)[0], 'healthcare')

    def test_ambiguous_clues_do_not_force_classification(self):
        obj = {**job('one','Business Partner'), 'description':'Working with an NHS trust and a retail bank.'}
        self.assertEqual(classify(obj), ('unclassified','unknown'))

    def test_counts_include_all_fetched_not_just_profile_matches(self):
        jobs = [{'industry':'technology','verdict':'REJECT'}, {'industry':'technology','verdict':'REVIEW'},
                {'industry':'energy-utilities','verdict':'SHORTLIST'}]
        counts = {x['id']:x for x in industry_counts(jobs)}
        self.assertEqual(counts['technology']['count'],2)
        self.assertEqual(counts['technology']['matched'],1)
        self.assertEqual(counts['energy-utilities']['matched'],1)

    def test_pipeline_uses_source_sector_and_keeps_rejected_results(self):
        sources = [{'name':'Example Bank','sector':'banking'}, {'name':'Example Factory','sector':'manufacturing'}]
        def fetch(src):
            return [job(src['name'].replace(' ','-'), 'Software Developer', src['name'])]
        results = scan_jobs(PROFILE, sources, fetcher=fetch)
        self.assertEqual(len(results['jobs']),2)
        self.assertEqual(results['counts']['REJECT'],2)
        self.assertEqual({j['company']:j['industry'] for j in results['jobs']},
                         {'Example Bank':'financial-services','Example Factory':'engineering-manufacturing'})
        self.assertEqual(sum(item['count'] for item in results['industries']),2)
        self.assertTrue(all('_source_sector' not in j for j in results['jobs']))

    def test_demo_includes_multiple_fictional_industries(self):
        scan = scan_jobs(PROFILE, [], demo=True)
        self.assertGreaterEqual(sum(i['count']>0 for i in scan['industries']),7)
        self.assertTrue(all(j['source']=='demo' for j in scan['jobs']))

    def test_public_source_industry_must_be_valid(self):
        parsed = parse_employer_url('https://jobs.lever.co/example','Test',sector='technology')
        self.assertEqual(parsed['sector'],'technology')
        with self.assertRaises(ValueError):
            parse_employer_url('https://jobs.lever.co/example','Test',sector='secret')

    def test_explicit_overseas_only_excluded_uk_ambiguous_retained(self):
        self.assertTrue(obviously_non_uk('Berlin, Germany'))
        self.assertTrue(obviously_non_uk('Remote (US)'))
        self.assertFalse(obviously_non_uk('London, UK / Berlin, Germany'))
        self.assertFalse(obviously_non_uk('Remote — eligibility not stated'))
        out = scan_jobs(PROFILE, [{'name':'Demo','sector':'technology'}],
                        fetcher=lambda src: [job('one','Programme Manager',location='Berlin, Germany'),
                                             job('two','Programme Manager',location='Remote')])
        self.assertEqual(len(out['jobs']),1)
        self.assertEqual(out['excluded_non_uk'],1)

    def test_default_source_registry_is_diverse_and_unique(self):
        sources = json.loads((ROOT/'config/sources.json').read_text())['sources']
        self.assertGreaterEqual(len(sources),15)
        self.assertGreaterEqual(len(set(classify({}, s['sector'])[0] for s in sources)),7)
        self.assertEqual(len(set((s['provider'],s['board'].casefold()) for s in sources)),len(sources))

    def test_ui_exposes_industry_carousel_controls(self):
        page = (ROOT/'uk_hunter/static/index.html').read_text()
        js = (ROOT/'uk_hunter/static/app.js').read_text()
        self.assertIn('id="industryRail"',page)
        self.assertIn('aria-pressed',js)
        self.assertIn("state.filter === 'all'",js)
        self.assertIn('renderIndustries()',js)


if __name__ == '__main__':
    unittest.main()
