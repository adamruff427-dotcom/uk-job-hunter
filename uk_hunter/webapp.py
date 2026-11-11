"""Local-first browser interface for UK Job Hunter.

No cloud accounts, analytics, uploads, external JavaScript, or application submission.
This server deliberately binds only to loopback and rejects non-loopback Host values.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import threading
import time
from typing import Any
from urllib.parse import urlsplit, unquote

from .cli import ROOT, default_profile_path, load_config
from .evaluate import evaluate
from .providers import fetch_feed, valid_job_link
from .industries import classify, industry_counts, LABELS
from .uk_scope import obviously_non_uk

STATIC = Path(__file__).resolve().parent / "static"
STATE_FILE = ROOT / "local_config" / "tracker.json"
PROFILE_FILE = ROOT / "local_config" / "search_profile.json"
SOURCES_FILE = ROOT / "config" / "sources.json"
LOCAL_SOURCES_FILE = ROOT / "local_config" / "sources.json"
PROFILE_EXAMPLE = ROOT / "config" / "profile.example.json"
STATUS = {"saved", "applied", "interview", "offer", "rejected", "closed", "dismissed"}
ALLOWED_LISTS = {
    "nearby_places", "hybrid_review_places", "excluded_commute_places",
    "preferred_sectors", "target_roles", "related_terms", "excluded_title_terms",
}


def validate_profile(obj: Any) -> dict:
    """Apply a fixed schema; do not allow arbitrary keys or huge values."""
    if not isinstance(obj, dict):
        raise ValueError("Profile must be a JSON object")
    example = load_config(PROFILE_EXAMPLE)
    profile = dict(example)
    if set(obj) - set(example):
        raise ValueError("Unknown profile settings")
    for key, value in obj.items():
        if key in ALLOWED_LISTS:
            if not isinstance(value, list) or len(value) > 60 or any(not isinstance(x, str) or len(x) > 120 for x in value):
                raise ValueError(f"Invalid list for {key}")
            profile[key] = [x.strip() for x in value if x.strip()]
        elif key in {"minimum_basic_salary_gbp", "preferred_basic_salary_gbp"}:
            if value is not None and (type(value) is not int or not 0 <= value <= 1_000_000):
                raise ValueError(f"Invalid salary in {key}")
            profile[key] = value
        elif key == "remote_first":
            if type(value) is not bool:
                raise ValueError("remote_first must be true or false")
            profile[key] = value
        elif key == "home_base":
            if not isinstance(value, str) or len(value) > 120:
                raise ValueError("Invalid home_base")
            profile[key] = value.strip()
    return profile


def read_profile() -> dict:
    return validate_profile(load_config(default_profile_path()))


def write_private_json(path: Path, obj: Any) -> None:
    """Atomic local-only write. Defaults to private 0600 on POSIX."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(obj, indent=2, ensure_ascii=False).encode("utf-8") + b"\n"
    if len(payload) > 512_000:
        raise ValueError("Local file too large")
    temp = path.with_name(path.name + ".tmp")
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        if hasattr(os, "fchmod"):
            os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as f:
            f.write(payload)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp, path)
    finally:
        if temp.exists():
            temp.unlink()


class Tracker:
    def __init__(self, path: Path = STATE_FILE):
        self.path = path
        self.lock = threading.Lock()

    def load(self) -> dict:
        if not self.path.exists():
            return {}
        value = load_config(self.path)
        return value if isinstance(value, dict) else {}

    def update(self, payload: Any) -> dict:
        if not isinstance(payload, dict):
            raise ValueError("Invalid tracker request")
        status = payload.get("status")
        job = payload.get("job")
        if status not in STATUS | {"remove"} or not isinstance(job, dict):
            raise ValueError("Invalid status or job")
        job_id = job.get("id")
        title, company, url = job.get("title"), job.get("company"), job.get("url")
        if not isinstance(job_id, str) or not 1 <= len(job_id) <= 250 or not re.fullmatch(r"[A-Za-z0-9:._/-]+", job_id):
            raise ValueError("Invalid job ID")
        if status != "remove" and (not isinstance(title, str) or not 1 <= len(title) <= 240 or not isinstance(company, str) or not 1 <= len(company) <= 160 or not valid_job_link(url)):
            raise ValueError("Invalid job metadata or link")
        notes = payload.get("notes", "")
        if not isinstance(notes, str) or len(notes) > 2500:
            raise ValueError("Notes must be at most 2500 characters")
        with self.lock:
            state = self.load()
            if status == "remove":
                state.pop(job_id, None)
            else:
                state[job_id] = {
                    "id": job_id,
                    "title": title,
                    "company": company,
                    "url": url,
                    "location": str(job.get("location") or "")[:240],
                    "salary_min": job.get("salary_min") if isinstance(job.get("salary_min"), int) else None,
                    "salary_max": job.get("salary_max") if isinstance(job.get("salary_max"), int) else None,
                    "status": status,
                    "notes": notes.strip(),
                    "industry": job.get("industry") if job.get("industry") in LABELS else "unclassified",
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
            if len(state) > 5000:
                raise ValueError("Tracker size limit exceeded")
            write_private_json(self.path, state)
            return state


def read_sources() -> list[dict]:
    path = LOCAL_SOURCES_FILE if LOCAL_SOURCES_FILE.exists() else SOURCES_FILE
    obj = load_config(path)
    sources = obj.get("sources")
    if not isinstance(sources, list) or len(sources) > 150:
        raise ValueError("Invalid employer sources")
    return sources


def parse_employer_url(url: str, name: str, job_path_prefix: str = "", sector: str = "unspecified") -> dict:
    """Parse known ATS boards or opt-in structured careers websites."""
    if not isinstance(url, str) or not isinstance(name, str) or not 1 <= len(name.strip()) <= 100:
        raise ValueError("Provide an employer name and an ATS careers URL")
    if sector != "unspecified" and sector not in LABELS:
        raise ValueError("Choose an industry from the provided list")
    parts = urlsplit(url.strip())
    if parts.scheme != "https" or parts.username or parts.password or parts.port:
        raise ValueError("The careers URL must be HTTPS with no credentials or custom port")
    hosts = {
        "job-boards.greenhouse.io": "greenhouse",
        "boards.greenhouse.io": "greenhouse",
        "jobs.lever.co": "lever",
        "jobs.ashbyhq.com": "ashby",
        "careers.smartrecruiters.com": "smartrecruiters",
    }
    provider = hosts.get((parts.hostname or "").lower())
    if not provider:
        from .website import validate_source
        new = {"name": name.strip(), "provider": "website", "url": url.strip(),
               "job_path_prefixes": [job_path_prefix.strip()], "max_details": 10,
               "sector": sector}
        validate_source(new)
        return new
    segments = [unquote(s) for s in parts.path.split("/") if s]
    if any(s in {".", ".."} for s in segments):
        raise ValueError("Unsafe careers path")
    board = segments[0] if segments else ""
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", board):
        raise ValueError("Could not identify a safe board slug")
    return {
        "name": name.strip(), "provider": provider, "board": board,
        "url": f"https://{parts.hostname}/{board}", "sector": sector,
    }


def update_sources(payload: Any) -> list[dict]:
    if not isinstance(payload, dict):
        raise ValueError("Invalid source request")
    action = payload.get("action")
    sources = read_sources()
    if action == "add":
        new = parse_employer_url(payload.get("url"), payload.get("name"), payload.get("job_path_prefix", ""), payload.get("sector", "unspecified"))
        if any(s.get("provider") == new["provider"] and (
                (new["provider"] == "website" and s.get("url", "").casefold() == new["url"].casefold()) or
                (new["provider"] != "website" and s.get("board", "").casefold() == new["board"].casefold())) for s in sources):
            raise ValueError("This employer board is already included")
        if len(sources) >= 150:
            raise ValueError("Maximum 150 sources")
        sources.append(new)
    elif action == "remove":
        board, provider, target_url = payload.get("board"), payload.get("provider"), payload.get("url")
        if not isinstance(provider, str) or (provider == "website" and not isinstance(target_url, str)) or (provider != "website" and not isinstance(board, str)):
            raise ValueError("A source identifier is required")
        original = len(sources)
        sources = [s for s in sources if not (s.get("provider") == provider and (
            s.get("url") == target_url if provider == "website" else s.get("board") == board))]
        if len(sources) == original:
            raise ValueError("Employer board was not found")
    else:
        raise ValueError("Unknown source operation")
    write_private_json(LOCAL_SOURCES_FILE, {"sources": sources})
    return sources


def scan_jobs(profile: dict, sources: list[dict], fetcher=fetch_feed, *, demo=False) -> dict:
    """Fetch configured employer boards in parallel and retain source failures."""
    profile = validate_profile(profile)
    active_sources = [s for s in sources if s.get("enabled", True) is not False]
    source_health: list[dict] = []
    if demo:
        jobs = demo_jobs()
        failures: list[str] = []
        reached = 0
    else:
        jobs, failures, reached = [], [], 0
        if active_sources:
            with ThreadPoolExecutor(max_workers=min(len(active_sources), 8)) as pool:
                futures = {pool.submit(fetcher, src): src for src in active_sources}
                for future in as_completed(futures):
                    src = futures[future]
                    name = str(src.get("name") or "Unknown source")[:100]
                    provider = str(src.get("provider") or "unknown")[:40]
                    try:
                        found = [item for item in future.result() if isinstance(item, dict)]
                        jobs.extend({**item, "_source_sector": src.get("sector")} for item in found)
                        source_health.append({"name": name, "provider": provider, "status": "ok", "raw_count": len(found)})
                        reached += 1
                    except Exception as exc:  # provider errors never count as zero jobs
                        error = str(exc)[:200]
                        failures.append(f"{name}: {error}")
                        source_health.append({"name": name, "provider": provider, "status": "error", "error": error})
        source_health.sort(key=lambda row: (row["status"] != "error", row["name"].casefold()))
    from .dedupe import unique_jobs
    output = []
    excluded_non_uk = 0
    for job in unique_jobs(jobs):
        if obviously_non_uk(job.get("location", "")):
            excluded_non_uk += 1
            continue
        try:
            category, basis = classify(job, job.get("_source_sector"))
            clean_job = {k: v for k, v in job.items() if k != "_source_sector"}
            evaluated = evaluate(clean_job, profile)
            evaluated["industry"], evaluated["industry_basis"] = category, basis
            output.append(evaluated)
        except (ValueError, TypeError, KeyError) as exc:
            failures.append(f"Unusable posting from {job.get('company', 'unknown source')}: {str(exc)[:100]}")
    priority = {"SHORTLIST": 0, "REVIEW": 1, "REJECT": 2, "SKIP_OLD": 3}
    output.sort(key=lambda j: (
        priority.get(j.get("verdict"), 4),
        -(1 if profile.get("remote_first") and (j.get("workplace_type") == "remote" or "remote" in str(j.get("location", "")).lower()) else 0),
        -j.get("score", 0), j.get("company", ""), j.get("title", "")
    ))
    counts = {key: sum(j.get("verdict") == key for j in output) for key in priority}
    return {
        "jobs": output,
        "counts": counts,
        "industries": industry_counts(output),
        "excluded_non_uk": excluded_non_uk,
        "errors": failures,
        "source_count": len(active_sources),
        "sources_reached": reached,
        "sources_disabled": len(sources) - len(active_sources),
        "source_health": source_health,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "demo": demo,
        "coverage_note": "Searches enabled sources, not the entire UK labour market. Wide-area APIs require credentials and permitted reuse; overseas-only roles are excluded, but unknown eligibility requires checking.",
    }


def demo_jobs() -> list[dict]:
    """Broad, explicitly fictional examples across sectors for UI exploration."""
    template = [
        ("one", "Risk Manager", "Example Bank", "Remote within the UK", "remote", 58000, 75000, "financial-services"),
        ("two", "Operations Manager", "Example Manufacturer", "Manchester, United Kingdom", "hybrid", 49000, 63000, "engineering-manufacturing"),
        ("three", "Change Manager", "Example NHS Trust", "Leeds, UK", "onsite", None, None, "healthcare"),
        ("four", "Senior Compliance Manager", "Example Finance", "London, UK", "hybrid", 71000, 82000, "financial-services"),
        ("five", "Software Developer", "Example Digital", "Remote within the UK", "remote", 48000, 66000, "technology"),
        ("six", "Project Manager", "Example Defence", "Bristol, UK", "hybrid", 54000, 69000, "defence-security"),
        ("seven", "Engineering Lead", "Example Windpower", "Cardiff, UK", "hybrid", 60000, 83000, "energy-utilities"),
        ("eight", "Policy Analyst", "Example Council", "Birmingham, UK", "onsite", 40000, 52000, "public-sector"),
        ("nine", "Supply Chain Manager", "Example Freight", "Liverpool, UK", "onsite", 47000, 61000, "transport-logistics"),
        ("ten", "Hotel Operations Director", "Example Hotels", "Edinburgh, UK", "hybrid", 65000, 85000, "hospitality-leisure"),
    ]
    return [{"id": "example:" + a, "title": b, "company": c, "location": d, "workplace_type": e,
             "salary_min": f, "salary_max": g, "url": "https://example.com/jobs/" + a,
             "description": "Fictional vacancy for demonstrating industry browsing. Not a real job.",
             "date": None, "source": "demo", "industry": sector}
            for a, b, c, d, e, f, g, sector in template]


class App(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address, *, tracker: Tracker | None = None):
        if address[0] not in {"127.0.0.1", "::1", "localhost"}:
            raise ValueError("For privacy, UK Job Hunter only serves on the local machine")
        super().__init__(address, Handler)
        self.tracker = tracker or Tracker()
        self.cache: dict[str, Any] | None = None
        self.cached_at = 0.0
        self.cache_lock = threading.Lock()


class Handler(BaseHTTPRequestHandler):
    server: App

    def log_message(self, format: str, *args: Any) -> None:
        # Do not print query parameters or candidate profile details into logs.
        print(f"[UK Job Hunter] {self.command} {urlsplit(self.path).path} {args[1] if len(args) > 1 else ''}")

    def _host_ok(self) -> bool:
        host = self.headers.get("Host", "").lower()
        return bool(re.fullmatch(r"(127\.0\.0\.1|localhost|\[::1\]):\d{1,5}", host))

    def _secure(self):
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self'; script-src 'self'; connect-src 'self'; img-src 'self' data:; object-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        self.send_header("Cache-Control", "no-store")

    def _bytes(self, content: bytes, status: int = 200, content_type: str = "application/json; charset=utf-8", attachment: str | None = None):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        if attachment:
            self.send_header("Content-Disposition", f'attachment; filename="{attachment}"')
        self._secure()
        self.end_headers()
        self.wfile.write(content)

    def _json(self, obj: Any, status=200, attachment=None):
        self._bytes(json.dumps(obj, ensure_ascii=False).encode("utf-8"), status, attachment=attachment)

    def do_GET(self):
        if not self._host_ok():
            return self._json({"error": "Local access only"}, 403)
        route = urlsplit(self.path).path
        if route in {"/", "/app.css", "/app.js"}:
            name = {"/": "index.html", "/app.css": "app.css", "/app.js": "app.js"}[route]
            media = {"index.html": "text/html", "app.css": "text/css", "app.js": "text/javascript"}[name]
            return self._bytes((STATIC / name).read_bytes(), content_type=media + "; charset=utf-8")
        if route == "/api/profile":
            try:
                return self._json(read_profile())
            except Exception as exc:
                return self._json({"error": f"Could not read profile: {exc}"}, 400)
        if route == "/api/tracker":
            return self._json(self.server.tracker.load())
        if route == "/api/sources":
            return self._json({"sources": read_sources()})
        if route == "/api/export":
            return self._json({"exported_at": datetime.now(timezone.utc).isoformat(), "tracker": self.server.tracker.load()}, attachment="uk-job-hunter-tracker.json")
        if route == "/api/jobs":
            demo = "demo=1" in urlsplit(self.path).query.split("&")
            try:
                profile = read_profile()
                sources = read_sources()
                if not isinstance(sources, list):
                    raise ValueError("Source list is invalid")
                if demo:
                    return self._json(scan_jobs(profile, sources, demo=True))
                with self.server.cache_lock:
                    if self.server.cache is not None and time.monotonic() - self.server.cached_at < 600:
                        return self._json(self.server.cache)
                    result = scan_jobs(profile, sources)
                    self.server.cache, self.server.cached_at = result, time.monotonic()
                    return self._json(result)
            except Exception as exc:
                return self._json({"error": f"Scan failed: {exc}"}, 500)
        return self._json({"error": "Not found"}, 404)

    def do_POST(self):
        if not self._host_ok():
            return self._json({"error": "Local access only"}, 403)
        origin = self.headers.get("Origin")
        if origin and origin != f"http://{self.headers.get('Host')}":
            return self._json({"error": "Cross-origin request rejected"}, 403)
        if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
            return self._json({"error": "JSON required"}, 415)
        try:
            size = int(self.headers.get("Content-Length", "-1"))
            if not 0 <= size <= 65536:
                raise ValueError("Invalid request size")
            payload = json.loads(self.rfile.read(size))
            route = urlsplit(self.path).path
            if route == "/api/profile":
                profile = validate_profile(payload)
                write_private_json(PROFILE_FILE, profile)
                with self.server.cache_lock:
                    self.server.cache = None
                return self._json({"ok": True})
            if route == "/api/tracker":
                return self._json({"ok": True, "tracker": self.server.tracker.update(payload)})
            if route == "/api/sources":
                sources = update_sources(payload)
                with self.server.cache_lock:
                    self.server.cache = None
                return self._json({"ok": True, "sources": sources})
            return self._json({"error": "Not found"}, 404)
        except (ValueError, UnicodeDecodeError, TypeError) as exc:
            return self._json({"error": str(exc)}, 400)


def serve(port=8765, *, open_browser=False):
    import webbrowser
    url = f"http://127.0.0.1:{port}"
    server = App(("127.0.0.1", port))
    print(f"UK Job Hunter local browser app: {url}")
    print("Your preferences and application tracker stay on this computer. Press Ctrl+C to stop.")
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever(poll_interval=0.3)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
