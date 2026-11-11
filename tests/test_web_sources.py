"""Deterministic website/ATS/API adapter tests; no external network required."""
import json
import unittest
from unittest.mock import patch

from uk_hunter.website import (
    _salary_gbp, _safe_page_link, _hostname, extract_jobposting, fetch_website_feed,
    validate_source, verify_public_dns,
)
from uk_hunter.extra_providers import fetch_adzuna, fetch_smartrecruiters, smartrecruiters_job
from uk_hunter.webapp import parse_employer_url, update_sources

BASE = "https://careers.example.org/careers"
SOURCE = {"name": "Example", "provider": "website", "url": BASE,
          "job_path_prefixes": ["/careers/jobs/"], "max_details": 5}


def posting_page(title="Risk Manager", location="London", expired=False):
    data = {"@context": "https://schema.org", "@type": "JobPosting", "title": title,
            "datePosted": "2026-11-09", "hiringOrganization": {"name": "Example Ltd"},
            "description": "<p>Risk controls and change work</p>",
            "jobLocation": {"address": {"addressLocality": location, "addressCountry": "GB"}},
            "baseSalary": {"@type": "MonetaryAmount", "currency": "GBP",
                           "value": {"@type": "QuantitativeValue", "unitText": "YEAR", "minValue": 54000, "maxValue": 68000}}}
    if expired:
        data["validThrough"] = "2020-01-01"
    return '<html><script type="application/ld+json">' + json.dumps(data) + '</script></html>'


class WebsiteAdapterTests(unittest.TestCase):
    def test_index_discovers_same_host_jobposting(self):
        listing = '<a href="/careers/jobs/risk-manager">Risk Manager</a><a href="https://other.com/jobs/x">Offsite</a>'
        pages = {BASE: listing, "https://careers.example.org/careers/jobs/risk-manager": posting_page()}
        requested = []
        def getter(url):
            requested.append(url)
            return pages[url]
        result = fetch_website_feed(SOURCE, fetcher=getter, robots_checker=lambda u: True, pause=lambda s: None)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["salary_min"], 54000)
        self.assertEqual(result[0]["company"], "Example Ltd")
        self.assertNotIn("other.com", " ".join(requested))

    def test_index_can_embed_jobposting(self):
        result = fetch_website_feed(SOURCE, fetcher=lambda u: posting_page(), robots_checker=lambda u: True, pause=lambda s: None)
        self.assertEqual(result[0]["source"], "website")

    def test_remote_without_uk_requirement_is_not_declared_uk(self):
        data = {"@type": "JobPosting", "title": "Remote Role", "jobLocationType": "TELECOMMUTE"}
        html = '<script type="application/ld+json">' + json.dumps(data) + '</script>'
        job = extract_jobposting(html, BASE, SOURCE)[0]
        self.assertIn("eligibility unknown", job["location"])

    def test_salary_without_annual_unit_stays_unknown(self):
        self.assertEqual(_salary_gbp({"baseSalary": {"currency": "GBP", "value": 5000}}), (None, None))

    def test_expired_job_not_returned(self):
        self.assertEqual(extract_jobposting(posting_page(expired=True), BASE, SOURCE), [])

    def test_no_jsonld_returns_clear_failure(self):
        with self.assertRaisesRegex(RuntimeError, "no structured JobPosting"):
            fetch_website_feed(SOURCE, fetcher=lambda u: "<div>No careers data</div>", robots_checker=lambda u: True)

    def test_robots_disallow_fails_closed(self):
        with self.assertRaisesRegex(RuntimeError, "robots.txt"):
            fetch_website_feed(SOURCE, fetcher=lambda u: posting_page(), robots_checker=lambda u: False)

    def test_link_rejects_offsite_and_unsafe_scheme(self):
        self.assertIsNone(_safe_page_link(BASE, "https://private.example.org/careers/jobs/x", "careers.example.org", ("/careers/jobs/",)))
        self.assertIsNone(_safe_page_link(BASE, "javascript:alert(1)", "careers.example.org", ("/careers/jobs/",)))
        self.assertIsNotNone(_safe_page_link(BASE, "/careers/jobs/x", "careers.example.org", ("/careers/jobs/",)))

    def test_reject_private_ip_and_unrestricted_paths(self):
        for url in ("https://127.0.0.1/careers", "https://localhost/careers", "https://x.local/careers", "http://careers.example.org"):
            with self.assertRaises(ValueError):
                _hostname(url)
        with self.assertRaises(ValueError):
            validate_source({**SOURCE, "job_path_prefixes": ["/"]})

    def test_dns_blocks_nonpublic_results(self):
        fake = [(2, 1, 6, "", ("10.0.0.3", 443))]
        with patch("uk_hunter.website.socket.getaddrinfo", return_value=fake):
            with self.assertRaisesRegex(RuntimeError, "non-public"):
                verify_public_dns("careers.example.org")


class PublicAPIAdapterTests(unittest.TestCase):
    def test_custom_website_requires_explicit_job_path(self):
        with self.assertRaises(ValueError):
            parse_employer_url(BASE, "Example")
        parsed = parse_employer_url(BASE, "Example", "/careers/jobs/")
        self.assertEqual(parsed["provider"], "website")
        self.assertEqual(parsed["job_path_prefixes"], ["/careers/jobs/"])

    def test_smartrecruiters_board_from_careers_url(self):
        source = parse_employer_url("https://careers.smartrecruiters.com/Wise", "Wise")
        self.assertEqual(source["provider"], "smartrecruiters")
        self.assertEqual(source["board"], "Wise")

    def test_smartrecruiters_list_and_detail(self):
        def reader(url):
            if "?limit=" in url:
                return {"content": [{"id": "123", "location": {"country": "GB"}},
                                    {"id": "987", "location": {"country": "US"}}]}
            return {"id": "123", "name": "Risk Manager", "applyUrl": "https://jobs.smartrecruiters.com/Wise/123",
                    "releasedDate": "2026-11-10", "location": {"city": "London", "country": "GB", "remote": True},
                    "jobAd": {"sections": {"jobDescription": {"text": "Risk oversight"}}}}
        results = fetch_smartrecruiters({"name": "Wise", "board": "Wise"}, reader=reader)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["date"], "2026-11-10")
        self.assertEqual(results[0]["workplace_type"], "remote")

    def test_smartrecruiters_no_fabricated_link(self):
        self.assertIsNone(smartrecruiters_job("Wise", "Wise", {"name": "Risk Manager", "id": "123"}))

    def test_adzuna_needs_credentials(self):
        with self.assertRaisesRegex(RuntimeError, "not enabled"):
            fetch_adzuna({"queries": ["risk manager"]}, environ={})

    def test_adzuna_predictions_do_not_count_as_basic_salary(self):
        def reader(url):
            self.assertIn("https://api.adzuna.com/", url)
            return {"results": [{"id": "a", "title": "Risk Manager", "redirect_url": "https://www.adzuna.co.uk/jobs/1",
                                 "company": {"display_name": "Example"}, "salary_min": 90000, "salary_max": 100000,
                                 "salary_is_predicted": True}]}
        result = fetch_adzuna({"queries": ["risk manager"]}, reader=reader,
                              environ={"ADZUNA_APP_ID": "test", "ADZUNA_APP_KEY": "test"})
        self.assertIsNone(result[0]["salary_min"])

    def test_adzuna_error_does_not_leak_credentials(self):
        def reader(url):
            raise RuntimeError("HTTP 403 " + url)
        try:
            fetch_adzuna({"queries": ["risk"]}, reader=reader, environ={"ADZUNA_APP_ID": "secret-id", "ADZUNA_APP_KEY": "secret-key"})
        except RuntimeError as exc:
            self.assertNotIn("secret-key", str(exc))
        else:
            self.fail("Expected a provider failure")

if __name__ == "__main__":
    unittest.main()

class DedupeTests(unittest.TestCase):
    def test_prefer_company_source_for_same_cross_provider_role(self):
        from uk_hunter.dedupe import unique_jobs
        base = {"company": "Example", "title": "Risk Manager", "location": "London, UK"}
        jobs = [dict(base, id="adzuna:1", url="https://adzuna.co.uk/1", source="adzuna"),
                dict(base, id="smartrecruiters:1", url="https://smartrecruiters.com/1", source="smartrecruiters")]
        result = unique_jobs(jobs)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["source"], "smartrecruiters")

    def test_same_company_can_have_two_distinct_role_ids(self):
        from uk_hunter.dedupe import unique_jobs
        base = {"company": "Example", "title": "Risk Manager", "location": "London, UK", "source": "greenhouse"}
        jobs = [dict(base, id="greenhouse:1", url="https://example.org/1"),
                dict(base, id="greenhouse:2", url="https://example.org/2")]
        self.assertEqual(len(unique_jobs(jobs)), 2)

class WebsiteSourceManagementTests(unittest.TestCase):
    def test_can_add_and_remove_custom_source_locally(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from uk_hunter import webapp
        with TemporaryDirectory() as directory:
            override = Path(directory) / "sources.json"
            template = Path(directory) / "template.json"
            template.write_text('{"sources": []}')
            with patch.object(webapp, "LOCAL_SOURCES_FILE", override), patch.object(webapp, "SOURCES_FILE", template):
                sources = update_sources({"action": "add", "name": "Example", "url": BASE,
                                          "job_path_prefix": "/careers/jobs/"})
                self.assertEqual(sources[0]["provider"], "website")
                self.assertTrue(override.exists())
                result = update_sources({"action": "remove", "provider": "website", "url": BASE})
                self.assertEqual(result, [])
