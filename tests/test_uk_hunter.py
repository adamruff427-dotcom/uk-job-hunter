import unittest
from datetime import date
from pathlib import Path
import io
import json
import tempfile
from contextlib import redirect_stdout
from unittest.mock import patch

from uk_hunter.evaluate import annual_salary_from_text, evaluate, loc_verdict
from uk_hunter.providers import endpoint, normalized, plain, valid_job_link, salary_from_ashby
from uk_hunter.cli import main, default_profile_path

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_PROFILE = json.loads((ROOT / "config" / "profile.example.json").read_text())
PROFILE = {**EXAMPLE_PROFILE,
    "minimum_basic_salary_gbp": 50000,
    "preferred_basic_salary_gbp": 60000,
    "nearby_places": ["Leeds", "Bradford"],
    "hybrid_review_places": ["York"],
    "excluded_commute_places": ["London"],
    "target_roles": ["operational controls lead", "risk manager", "governance manager"],
    "related_terms": ["governance", "risk", "controls"],
    "excluded_title_terms": ["data scientist", "director", "software engineer"]
}


def make_job(**overrides):
    base = {
        "id": "ashby:griffin:abc", "title": "Operational Controls Lead", "company": "Griffin",
        "location": "London or remote within the UK", "url": "https://jobs.ashbyhq.com/griffin/abc",
        "date": None, "description": "", "workplace_type": "remote",
        "salary_min": 60000, "salary_max": 75000, "source": "ashby",
    }
    base.update(overrides)
    return base


class EvaluateTests(unittest.TestCase):
    def test_remote_explicit_uk_shortlists_with_verified_salary(self):
        result = evaluate(make_job(), PROFILE)
        self.assertEqual(result["verdict"], "SHORTLIST")
        self.assertEqual(result["score"], 100)

    def test_salary_unknown_requires_review(self):
        result = evaluate(make_job(salary_min=None, salary_max=None), PROFILE)
        self.assertEqual(result["verdict"], "REVIEW")
        self.assertEqual(result["salary_gate"], "REVIEW")

    def test_below_floor_is_rejected(self):
        result = evaluate(make_job(salary_min=35000, salary_max=49000), PROFILE)
        self.assertEqual(result["verdict"], "REJECT")

    def test_band_spanning_floor_needs_review(self):
        result = evaluate(make_job(salary_min=45000, salary_max=65000), PROFILE)
        self.assertEqual(result["verdict"], "REVIEW")

    def test_london_hybrid_fails(self):
        result = evaluate(make_job(location="London", workplace_type="hybrid"), PROFILE)
        self.assertEqual(result["verdict"], "REJECT")

    def test_york_hybrid_needs_review(self):
        result = evaluate(make_job(location="York", workplace_type="hybrid"), PROFILE)
        self.assertEqual(result["verdict"], "REVIEW")

    def test_unknown_remote_eligibility_stays_review(self):
        self.assertEqual(loc_verdict("Remote", "remote", PROFILE)[0], "REVIEW")

    def test_nonuk_remote_fails(self):
        self.assertEqual(loc_verdict("Remote (United States)", "remote", PROFILE)[0], "FAIL")

    def test_clear_nonuk_location_fails(self):
        self.assertEqual(loc_verdict("Dublin", "hybrid", PROFILE)[0], "FAIL")

    def test_public_default_no_salary_floor(self):
        result = evaluate(make_job(title="Risk Manager", salary_min=None, salary_max=None), EXAMPLE_PROFILE)
        self.assertEqual(result["salary_gate"], "PASS")

    def test_public_default_does_not_reject_london_commuters(self):
        result = evaluate(make_job(title="Risk Manager", location="London", workplace_type="hybrid"), EXAMPLE_PROFILE)
        self.assertEqual(result["location_gate"], "REVIEW")

    def test_leeds_is_approved_only_when_configured(self):
        self.assertEqual(loc_verdict("Leeds", "hybrid", PROFILE)[0], "PASS")
        self.assertEqual(loc_verdict("Leeds", "hybrid", EXAMPLE_PROFILE)[0], "REVIEW")

    def test_partial_city_does_not_match(self):
        self.assertEqual(loc_verdict("New York", "hybrid", PROFILE)[0], "FAIL")
        self.assertEqual(loc_verdict("Bathgate", "hybrid", {**PROFILE, "nearby_places": ["Bath"]})[0], "REVIEW")

    def test_director_is_not_an_automatic_fit(self):
        self.assertEqual(evaluate(make_job(title="Director of Operational Controls"), PROFILE)["verdict"], "REJECT")

    def test_unrelated_us_city_fails(self):
        self.assertEqual(evaluate(make_job(location="San Francisco", workplace_type="onsite"), PROFILE)["verdict"], "REJECT")

    def test_unsupported_specialism_rejects(self):
        result = evaluate(make_job(title="Senior Data Scientist"), PROFILE)
        self.assertEqual(result["verdict"], "REJECT")

    def test_adjacent_not_automatically_shortlisted(self):
        result = evaluate(make_job(title="Senior Governance Adviser"), PROFILE)
        self.assertEqual(result["verdict"], "REVIEW")

    def test_date_age_respected_if_known(self):
        result = evaluate(make_job(date="2026-01-01"), PROFILE, days=14, today=date(2026, 11, 11))
        self.assertEqual(result["verdict"], "SKIP_OLD")

    def test_missing_date_not_treated_as_old(self):
        result = evaluate(make_job(date=None), PROFILE, days=14, today=date(2026, 11, 11))
        self.assertEqual(result["verdict"], "SHORTLIST")


class SalaryTests(unittest.TestCase):
    def test_salary_band(self):
        self.assertEqual(annual_salary_from_text("Salary: £60,000 - £75,000 per year"), (60000, 75000))

    def test_k_suffix_salary_band(self):
        self.assertEqual(annual_salary_from_text("Basic salary £55k to £70k"), (55000, 70000))

    def test_ote_not_base(self):
        self.assertEqual(annual_salary_from_text("Salary OTE £80,000 with commission"), (None, None))

    def test_bonus_not_salary(self):
        self.assertEqual(annual_salary_from_text("Annual bonus up to £100,000"), (None, None))

    def test_ashby_salary_is_base(self):
        job = {"compensation": {"summaryComponents": [{"compensationType": "Salary", "currencyCode": "GBP", "interval": "1 YEAR", "minValue": 58000, "maxValue": 69000}]}}
        self.assertEqual(salary_from_ashby(job), (58000, 69000))


class PublicReleaseSafetyTests(unittest.TestCase):
    def test_example_has_no_personal_location_or_salary(self):
        self.assertEqual(EXAMPLE_PROFILE["home_base"], "")
        self.assertIsNone(EXAMPLE_PROFILE["minimum_basic_salary_gbp"])
        self.assertEqual(EXAMPLE_PROFILE["nearby_places"], [])
        self.assertEqual(EXAMPLE_PROFILE["hybrid_review_places"], [])

    def test_personal_profiles_are_gitignored(self):
        ignore = (ROOT / ".gitignore").read_text()
        for rule in ("local_config/", "config/search_profile.json", "private/", ".env", "reports/"):
            self.assertIn(rule, ignore)


class SourceTests(unittest.TestCase):
    def test_no_url_injection(self):
        with self.assertRaises(ValueError):
            endpoint("greenhouse", "monzo/../evil")

    def test_no_http_or_local_links(self):
        self.assertIsNone(valid_job_link("http://jobs.ashbyhq.com/x"))
        self.assertIsNone(valid_job_link("https://localhost/internal"))
        self.assertIsNone(valid_job_link("https://user:pass@foo.com/"))

    def test_greenhouse_updated_at_is_not_posted_date(self):
        job = normalized("Monzo", "greenhouse", "monzo", {"id": 2, "title": "Change Lead", "absolute_url": "https://job-boards.greenhouse.io/monzo/jobs/2", "updated_at": "2026-11-11T10:00:00Z"})
        self.assertIsNone(job["date"])

    def test_lever_created_at_is_date(self):
        job = normalized("Octopus", "lever", "octoenergy", {"id": "x", "text": "Risk Manager", "hostedUrl": "https://jobs.lever.co/octoenergy/x", "createdAt": 1794355200000, "categories": {"location": "Remote (GB)"}})
        self.assertEqual(job["date"], "2026-11-11")

    def test_ashby_unlisted_is_suppressed(self):
        self.assertIsNone(normalized("Griffin", "ashby", "griffin", {"title": "Hidden", "isListed": False, "jobUrl": "https://jobs.ashbyhq.com/griffin/hidden"}))

    def test_html_removes_script(self):
        self.assertNotIn("PROMPT", plain("<p>Job duties</p><script>PROMPT</script>"))

    def test_init_creates_local_untracked_profile_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as root:
            target = Path(root) / "local_config" / "search_profile.json"
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(["init", "--output", str(target)]), 0)
            self.assertEqual(json.loads(target.read_text()), EXAMPLE_PROFILE)
            with patch("sys.stderr", io.StringIO()):
                self.assertEqual(main(["init", "--output", str(target)]), 1)

    def test_legacy_private_profile_takes_precedence_over_public_example(self):
        with tempfile.TemporaryDirectory() as root:
            from uk_hunter import cli
            tmp = Path(root)
            (tmp / "config").mkdir()
            (tmp / "config/profile.example.json").write_text('{"minimum_basic_salary_gbp": null}')
            (tmp / "config/search_profile.json").write_text('{"minimum_basic_salary_gbp": 50000}')
            with patch.object(cli, "ROOT", tmp):
                self.assertEqual(default_profile_path(), tmp / "config/search_profile.json")
                (tmp / "local_config").mkdir()
                (tmp / "local_config/search_profile.json").write_text('{"minimum_basic_salary_gbp": 60000}')
                self.assertEqual(default_profile_path(), tmp / "local_config/search_profile.json")

    def test_empty_sources_config_is_error(self):
        with tempfile.TemporaryDirectory() as root:
            conf = Path(root) / "sources.json"
            conf.write_text('{"sources": []}')
            with patch("sys.stderr", io.StringIO()):
                self.assertEqual(main(["search", "--sources", str(conf)]), 1)

    def test_end_to_end_json_shortlist_is_machine_readable(self):
        feed = [make_job(title="Risk Manager")]
        stdout = io.StringIO()
        with patch("uk_hunter.cli.fetch_feed", return_value=feed), redirect_stdout(stdout):
            self.assertEqual(main(["search", "--format", "json"]), 0)
        data = json.loads(stdout.getvalue())
        self.assertEqual(data["results"][0]["title"], "Risk Manager")
        self.assertEqual(data["results"][0]["fit"], "shortlist")
        self.assertEqual(len(data["results"]), 1)

    def test_all_sources_failed_returns_nonzero(self):
        with patch("uk_hunter.cli.fetch_feed", side_effect=RuntimeError("offline")):
            with patch("sys.stdout"):
                self.assertEqual(main(["search", "--format", "json"]), 2)


if __name__ == "__main__":
    unittest.main()

class InstallerTests(unittest.TestCase):
    def test_overlay_installs_without_discarding_upstream_workflows(self):
        from install_into_upstream import install
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            (target / ".claude/skills/job-scraper").mkdir(parents=True)
            (target / ".agents/skills/linkedin-search").mkdir(parents=True)
            (target / "tests").mkdir()
            (target / "AGENTS.md").write_text("# Original upstream instructions\n")
            (target / ".claude/skills/job-scraper/SKILL.md").write_text("original scraper\n")
            (target / ".claude/skills/job-scraper/search-queries.md").write_text("original queries\n")
            (target / ".agents/skills/linkedin-search/SKILL.md").write_text("---\nenabled: true\n---\n")
            (target / ".claude/settings.json").write_text('{"permissions":{"allow":["Bash(existing:*)"]}}')
            (target / ".gitignore").write_text(".env\n")
            (target / "config").mkdir()
            (target / "config/search_profile.json").write_text('{"example": "personal local override"}')
            first = install(target)
            self.assertTrue(first)
            self.assertTrue((target / "uk_hunter/cli.py").exists())
            self.assertEqual((target / "config/search_profile.json").read_text(), '{"example": "personal local override"}')
            self.assertTrue((target / "tests/test_uk_hunter_extension.py").exists())
            self.assertTrue((target / "UK_JOB_HUNTER.md").exists())
            self.assertIn("enabled: false", (target / ".agents/skills/linkedin-search/SKILL.md").read_text())
            self.assertIn("original queries", (target / ".claude/skills/job-scraper/search-queries.pre-uk.md").read_text())
            self.assertEqual((target / ".claude/skills/job-scraper/SKILL.md").read_text(), "original scraper\n")
            settings = json.loads((target / ".claude/settings.json").read_text())
            self.assertIn("Bash(existing:*)", settings["permissions"]["allow"])
            self.assertTrue(any("uk-ats-search" in x for x in settings["permissions"]["allow"]))
            install(target)
            self.assertEqual((target / "AGENTS.md").read_text().count("## UK job-search extension"), 1)
