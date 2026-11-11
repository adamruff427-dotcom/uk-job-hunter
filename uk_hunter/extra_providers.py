"""Additional documented public and licensed UK job source adapters.

SmartRecruiters uses its public company Posting API. Adzuna requires a user's
API credentials and appropriate agreement; we do not include/ship credentials.
"""
from __future__ import annotations

import json
import os
import re
import base64
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, quote
from urllib.request import Request, build_opener, HTTPRedirectHandler
from typing import Any, Callable

from .providers import plain, valid_job_link, iso_date, amount_gbp


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def read_public_json(url: str, timeout: int = 15) -> Any:
    """Only call this with endpoints built from fixed provider hosts."""
    request = Request(url, headers={"Accept": "application/json", "User-Agent": "UKJobHunter/0.3"}, method="GET")
    try:
        with build_opener(NoRedirect()).open(request, timeout=timeout) as r:
            if r.geturl() != url:
                raise RuntimeError("Unexpected provider redirect")
            raw = r.read(10_000_001)
    except (HTTPError, URLError, TimeoutError) as exc:
        # A credentialled request may contain an API key in its URL; never log it.
        raise RuntimeError(f"Provider request failed ({type(exc).__name__})") from exc
    if len(raw) > 10_000_000:
        raise RuntimeError("Provider response exceeds size limit")
    try:
        return json.loads(raw)
    except (ValueError, UnicodeDecodeError) as exc:
        raise RuntimeError("Provider returned invalid JSON") from exc


def smartrecruiters_job(company: str, board: str, obj: dict) -> dict | None:
    title = obj.get("name")
    job_id = obj.get("id")
    link = valid_job_link(obj.get("applyUrl"))
    if not title or not job_id or not link or obj.get("active") is False:
        return None
    loc = obj.get("location") or {}
    place = ", ".join(str(loc[k]) for k in ("city", "region", "country") if loc.get(k))
    kind = "remote" if loc.get("remote") is True else "unknown"
    sections = ((obj.get("jobAd") or {}).get("sections") or {})
    desc = "\n".join(str(s.get("text") or "") for s in sections.values() if isinstance(s, dict))
    return {"id": f"smartrecruiters:{board}:{job_id}", "title": str(title),
            "company": company, "location": place, "url": link, "date": iso_date(obj.get("releasedDate")),
            "description": plain(desc), "workplace_type": kind,
            "salary_min": None, "salary_max": None, "source": "smartrecruiters"}


def fetch_smartrecruiters(source: dict, *, reader: Callable[[str], Any] = read_public_json) -> list[dict]:
    board = source.get("board")
    if not isinstance(board, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", board):
        raise ValueError("Invalid SmartRecruiters board identifier")
    max_details = source.get("max_details", 25)
    if type(max_details) is not int or not 1 <= max_details <= 50:
        raise ValueError("SmartRecruiters max_details must be 1..50")
    base = f"https://api.smartrecruiters.com/v1/companies/{quote(board, safe='')}/postings"
    listing = reader(base + "?limit=100&offset=0&destination=PUBLIC")
    if not isinstance(listing, dict) or not isinstance(listing.get("content"), list):
        raise RuntimeError("SmartRecruiters list response has unexpected structure")
    jobs = []
    for item in listing["content"]:
        if not isinstance(item, dict):
            continue
        country = str((item.get("location") or {}).get("country") or "").casefold()
        # Explicitly non-UK listings are not appropriate for a UK-focused search.
        # A merely 'remote' US job does not imply UK eligibility.
        if country and country not in {"gb", "uk", "united kingdom", "great britain"}:
            continue
        job_id = str(item.get("id") or "")
        if not re.fullmatch(r"[A-Za-z0-9-]{1,90}", job_id):
            continue
        if len(jobs) >= max_details:
            break
        try:
            detail = reader(base + "/" + quote(job_id, safe=""))
            if isinstance(detail, dict):
                result = smartrecruiters_job(source["name"], board, detail)
                if result:
                    jobs.append(result)
        except RuntimeError:
            continue
    return jobs


def adzuna_job(item: dict) -> dict | None:
    link = valid_job_link(item.get("redirect_url"))
    if not link or not item.get("title") or not item.get("id"):
        return None
    loc = item.get("location") or {}
    area = loc.get("area") or []
    location = ", ".join(map(str, reversed(area[-3:]))) if area else str(loc.get("display_name") or "")
    company = item.get("company") or {}
    # Adzuna salary fields can be estimated. Until the employer's advert is
    # checked we do not treat them as verified basic pay for a salary pass.
    return {"id": f"adzuna:{item['id']}", "title": str(item['title']),
            "company": str(company.get("display_name") or "Unknown employer"),
            "location": location, "url": link, "date": iso_date(item.get("created")),
            "description": plain(item.get("description", "")), "workplace_type": "unknown",
            "salary_min": None, "salary_max": None, "source": "adzuna"}


def _bounded_int(source: dict, key: str, default: int, lower: int, upper: int) -> int:
    value = source.get(key, default)
    if type(value) is not int or not lower <= value <= upper:
        raise ValueError(f"{key} must be between {lower} and {upper}")
    return value


def reed_job(item: dict) -> dict | None:
    """Use Reed's advertised values cautiously: search lacks a pay-period guarantee."""
    job_id = item.get("jobId")
    title = item.get("jobTitle")
    if not title or not isinstance(job_id, int) or job_id < 1:
        return None
    company = str(item.get("employerName") or "Unknown employer")
    title_slug = re.sub(r"[^a-z0-9]+", "-", str(title).casefold()).strip("-")[:120]
    url = valid_job_link(item.get("jobUrl")) or f"https://www.reed.co.uk/jobs/{title_slug}/{job_id}"
    # Reed search salary fields have no reliable annual period. Never present
    # an hourly/day rate as annual basic pay or a guaranteed minimum salary.
    return {"id": f"reed:{job_id}", "title": str(title), "company": company,
            "location": str(item.get("locationName") or ""), "url": url,
            "date": iso_date(item.get("date")), "description": plain(item.get("jobDescription") or ""),
            "workplace_type": "unknown", "salary_min": None, "salary_max": None,
            "source": "reed"}


def read_reed_json(url: str, key: str, timeout: int = 15) -> Any:
    """Credentialed Reed Jobseeker API request to a fixed vendor domain."""
    if not url.startswith("https://www.reed.co.uk/api/1.0/search?"):
        raise ValueError("Unsupported Reed API URL")
    auth = base64.b64encode((key + ":").encode("utf-8")).decode("ascii")
    request = Request(url, headers={"Accept": "application/json", "Authorization": "Basic " + auth,
                                    "User-Agent": "UKJobHunterOpenSource/0.5"}, method="GET")
    try:
        with build_opener(NoRedirect()).open(request, timeout=timeout) as r:
            if r.geturl() != url:
                raise RuntimeError("Unexpected Reed redirect")
            raw = r.read(10_000_001)
    except (HTTPError, URLError, TimeoutError):
        # Do not expose the request, auth header or secret in any exception.
        raise RuntimeError("Reed API unavailable or not authorised") from None
    if len(raw) > 10_000_000:
        raise RuntimeError("Reed API response exceeds safety limit")
    try:
        return json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        raise RuntimeError("Reed API response is not JSON") from None


def fetch_reed(source: dict, *, reader: Callable[[str, str], Any] = read_reed_json,
               environ: dict | None = None) -> list[dict]:
    env = os.environ if environ is None else environ
    key = env.get("REED_API_KEY")
    if not key:
        raise RuntimeError("Reed is not enabled: configure REED_API_KEY and verify API usage rights")
    queries = source.get("queries", [""])
    if not isinstance(queries, list) or not 1 <= len(queries) <= 12 or any(
            not isinstance(q, str) or len(q) > 100 for q in queries):
        raise ValueError("Reed requires 1..12 search queries (blank means broad search)")
    pages = _bounded_int(source, "max_pages", 2, 1, 6)
    per_page = _bounded_int(source, "results_per_page", 100, 1, 100)
    results: list[dict] = []
    for query in queries:
        for page in range(pages):
            params = {"resultsToTake": per_page, "resultsToSkip": page * per_page}
            if query.strip():
                params["keywords"] = query.strip()
            url = "https://www.reed.co.uk/api/1.0/search?" + urlencode(params)
            try:
                payload = reader(url, key)
            except Exception:
                raise RuntimeError(f"Reed search failed for query={query!r}; check access and rate limits") from None
            if not isinstance(payload, dict) or not isinstance(payload.get("results"), list):
                raise RuntimeError("Reed search response has unexpected schema")
            rows = payload["results"]
            for item in rows:
                if isinstance(item, dict):
                    job = reed_job(item)
                    if job:
                        results.append(job)
            if len(rows) < per_page:
                break
    return list({job["id"]: job for job in results}.values())


def fetch_adzuna(source: dict, *, reader: Callable[[str], Any] = read_public_json,
                 environ: dict | None = None) -> list[dict]:
    env = os.environ if environ is None else environ
    app_id, app_key = env.get("ADZUNA_APP_ID"), env.get("ADZUNA_APP_KEY")
    if not app_id or not app_key:
        raise RuntimeError("Adzuna is not enabled: set ADZUNA_APP_ID and ADZUNA_APP_KEY and confirm licensing")
    queries = source.get("queries", [""])
    if not isinstance(queries, list) or not 1 <= len(queries) <= 12 or any(
            not isinstance(q, str) or len(q) > 100 for q in queries):
        raise ValueError("Adzuna requires 1..12 search queries (blank means broad search)")
    pages = _bounded_int(source, "max_pages", 2, 1, 6)
    per_page = _bounded_int(source, "results_per_page", 50, 1, 50)
    results: list[dict] = []
    for query in queries:
        for page in range(1, pages + 1):
            params = {"app_id": app_id, "app_key": app_key, "results_per_page": per_page,
                      "content-type": "application/json", "sort_by": "date"}
            if query.strip():
                params["what"] = query.strip()
            url = f"https://api.adzuna.com/v1/api/jobs/gb/search/{page}?" + urlencode(params)
            try:
                payload = reader(url)
            except Exception:
                # The URL contains app_id/app_key; never forward underlying exception.
                raise RuntimeError(f"Adzuna search failed for query={query!r}; check credentials/rate limits") from None
            if not isinstance(payload, dict) or not isinstance(payload.get("results"), list):
                raise RuntimeError("Adzuna response has unexpected structure")
            rows = payload["results"]
            for item in rows:
                if isinstance(item, dict):
                    job = adzuna_job(item)
                    if job:
                        results.append(job)
            if len(rows) < per_page:
                break
    return list({job["id"]: job for job in results}.values())
