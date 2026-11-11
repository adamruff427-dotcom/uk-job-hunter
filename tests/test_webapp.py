"""Public local-browser app: security and functional contract tests."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import threading
import unittest
from http.client import HTTPConnection
from unittest.mock import patch

from uk_hunter import webapp

EXAMPLE = json.loads((webapp.ROOT / "config/profile.example.json").read_text())


class ProfileValidationTests(unittest.TestCase):
    def test_public_profile_is_valid(self):
        self.assertIsNone(webapp.validate_profile(EXAMPLE)["minimum_basic_salary_gbp"])

    def test_rejects_extra_data_fields(self):
        with self.assertRaises(ValueError):
            webapp.validate_profile({"secret_token": "do not store me"})

    def test_rejects_string_or_boolean_salary(self):
        for bad in ("£50,000", True, -1, 2_000_000):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                webapp.validate_profile({"minimum_basic_salary_gbp": bad})

    def test_rejects_oversized_lists(self):
        with self.assertRaises(ValueError):
            webapp.validate_profile({"target_roles": ["role"] * 70})


class SourceControlTests(unittest.TestCase):
    def test_only_known_ats_urls_allowed(self):
        tests = [
            ("https://job-boards.greenhouse.io/monzo", "greenhouse", "monzo"),
            ("https://jobs.ashbyhq.com/griffin/xyz", "ashby", "griffin"),
            ("https://jobs.lever.co/octoenergy", "lever", "octoenergy"),
        ]
        for url, provider, board in tests:
            with self.subTest(url=url):
                result = webapp.parse_employer_url(url, "Employer")
                self.assertEqual(result["provider"], provider)
                self.assertEqual(result["board"], board)

    def test_rejects_untrusted_urls(self):
        for url in (
            "http://jobs.lever.co/company", "https://jobs.lever.co.evil.com/foo",
            "https://jobs.ashbyhq.com@evil.com/bar", "https://localhost/jobs",
            "https://jobs.lever.co/company/../../other", "https://jobs.lever.co:8443/company",
        ):
            with self.subTest(url=url), self.assertRaises(ValueError):
                webapp.parse_employer_url(url, "Employer")

    def test_source_changes_only_touch_private_override(self):
        with TemporaryDirectory() as folder:
            tmp = Path(folder) / "sources.json"
            with patch.object(webapp, "LOCAL_SOURCES_FILE", tmp):
                with patch.object(webapp, "SOURCES_FILE", Path(folder) / "defaults.json"):
                    (Path(folder) / "defaults.json").write_text('{"sources": []}')
                    sources = webapp.update_sources({"action":"add", "name":"Example", "url":"https://jobs.lever.co/example"})
                    self.assertEqual(len(sources), 1)
                    with self.assertRaises(ValueError):
                        webapp.update_sources({"action":"add", "name":"Example", "url":"https://jobs.lever.co/example"})
                    self.assertEqual(len(webapp.update_sources({"action":"remove", "provider":"lever", "board":"example"})), 0)


class TrackerTests(unittest.TestCase):
    def test_local_save_update_remove_and_no_description(self):
        with TemporaryDirectory() as folder:
            tracker = webapp.Tracker(Path(folder) / "tracker.json")
            job = {"id":"greenhouse:example:1", "title":"Risk Manager", "company":"Example", "location":"UK", "url":"https://example.com/job/1", "description":"Do not persist full adverts"}
            tracker.update({"job":job,"status":"saved","notes":"Call recruiter"})
            self.assertEqual(tracker.load()[job["id"]]["notes"], "Call recruiter")
            self.assertNotIn("description", tracker.load()[job["id"]])
            tracker.update({"job":job,"status":"applied","notes":"Applied today"})
            self.assertEqual(tracker.load()[job["id"]]["status"], "applied")
            tracker.update({"job":{"id":job["id"]},"status":"remove"})
            self.assertEqual(tracker.load(), {})

    def test_tracker_rejects_invalid_status_and_url(self):
        with TemporaryDirectory() as folder:
            tracker = webapp.Tracker(Path(folder) / "tracker.json")
            for status, url in (("auto_applied", "https://example.com"), ("saved", "http://localhost")):
                with self.subTest(status=status), self.assertRaises(ValueError):
                    tracker.update({"status":status,"job":{"id":"x","title":"Test","company":"Example","url":url}})


class ScanTests(unittest.TestCase):
    def test_demo_is_clearly_fictional(self):
        result = webapp.scan_jobs(EXAMPLE, [{"name":"Never fetched"}], demo=True)
        self.assertTrue(result["demo"])
        self.assertEqual(result["sources_reached"],0)
        self.assertTrue(all(j["source"] == "demo" for j in result["jobs"]))

    def test_unavailable_sources_are_reported(self):
        def broken(src): raise RuntimeError("server unavailable")
        result = webapp.scan_jobs(EXAMPLE,[{"name":"A"},{"name":"B"}],fetcher=broken)
        self.assertEqual(result["sources_reached"],0)
        self.assertEqual(len(result["errors"]),2)
        self.assertEqual(result["jobs"],[])

    def test_remote_first_sorting(self):
        base = {"id":"one","title":"Risk Manager","company":"Employer", "url":"https://example.com/1",
                "date":None,"description":"","salary_min":50000,"salary_max":80000,"source":"test"}
        def local(src):
            return [{**base,"id":"onsite","workplace_type":"onsite","location":"Leeds, UK"},
                    {**base,"id":"remote","workplace_type":"remote","location":"Remote within the UK"}]
        prof = {**EXAMPLE,"nearby_places":["Leeds"],"remote_first":True}
        result=webapp.scan_jobs(prof,[{"name":"Employer"}],fetcher=local)
        self.assertEqual(result["jobs"][0]["id"],"remote")


class HTTPTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        tracker = webapp.Tracker(Path(self.tmp.name) / "tracker.json")
        self.server = webapp.App(("127.0.0.1",0),tracker=tracker)
        self.addCleanup(self.server.server_close)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()
        self.addCleanup(self.server.shutdown)
        self.port=self.server.server_address[1]

    def call(self, method, path, data=None, headers=None):
        conn=HTTPConnection("127.0.0.1",self.port,timeout=3)
        body=json.dumps(data) if data is not None else None
        headers=headers or {}
        if body is not None:headers={"Content-Type":"application/json",**headers}
        conn.request(method,path,body=body,headers=headers)
        response=conn.getresponse()
        status=response.status
        raw=response.read()
        conn.close()
        return status,raw,response

    def test_serves_app_and_javascript(self):
        status,raw,_=self.call("GET","/")
        self.assertEqual(status,200)
        self.assertIn(b"UK Job Hunter",raw)
        status,raw,_=self.call("GET","/app.js")
        self.assertEqual(status,200)
        self.assertIn(b"renderTracker",raw)

    def test_demo_jobs_without_network(self):
        status,raw,_=self.call("GET","/api/jobs?demo=1")
        data=json.loads(raw)
        self.assertEqual(status,200)
        self.assertTrue(data["demo"])
        self.assertGreater(len(data["jobs"]),0)

    def test_origin_rejected(self):
        status,raw,_=self.call("POST","/api/tracker",{"x":1},{"Origin":"https://evil.example"})
        self.assertEqual(status,403)

    def test_host_rejected(self):
        status,raw,_=self.call("GET","/api/profile",headers={"Host":"evil.example"})
        self.assertEqual(status,403)

    def test_local_only_server(self):
        with self.assertRaises(ValueError):
            webapp.App(("0.0.0.0",0))

if __name__ == "__main__": unittest.main()
