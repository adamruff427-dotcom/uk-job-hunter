"""Read-only adapters for official public ATS feeds.

No application submission, authenticated scraping or arbitrary URL fetching.
The provider host is hard-coded; the board is validated as a single path segment.
"""
from __future__ import annotations

from datetime import datetime, timezone
import html
from html.parser import HTMLParser
import json
import re
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen


class HTMLText(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.text: list[str] = []
        self.suppressed = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript"}:
            self.suppressed += 1
        if tag in {"p", "br", "li", "div", "h1", "h2", "h3"}:
            self.text.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript"} and self.suppressed:
            self.suppressed -= 1

    def handle_data(self, data: str) -> None:
        if not self.suppressed:
            self.text.append(data)


def plain(value: Any) -> str:
    parser = HTMLText()
    parser.feed(html.unescape(str(value or "")))
    parser.close()
    return re.sub(r"[ \t]+", " ", "".join(parser.text)).strip()


def valid_job_link(url: Any) -> str | None:
    if not isinstance(url, str):
        return None
    u = urlsplit(url)
    if u.scheme != "https" or not u.hostname or u.username or u.password:
        return None
    if u.hostname in {"localhost", "127.0.0.1", "0.0.0.0"} or u.hostname.endswith(".local"):
        return None
    return url


def iso_date(value: Any) -> str | None:
    """Only accepted *posted/created* timestamps, never arbitrary updated_at."""
    if isinstance(value, (int, float)):
        if value > 10**12:
            value /= 1000
        try:
            return datetime.fromtimestamp(value, tz=timezone.utc).date().isoformat()
        except (ValueError, OverflowError, OSError):
            return None
    if isinstance(value, str) and re.match(r"^\d{4}-\d{2}-\d{2}", value):
        return value[:10]
    return None


def amount_gbp(value: Any) -> int | None:
    try:
        val = int(float(value))
        return val if val >= 1000 else None
    except (TypeError, ValueError, OverflowError):
        return None


def salary_from_ashby(job: dict) -> tuple[int | None, int | None]:
    comp = job.get("compensation") or {}
    for tier in comp.get("compensationTiers") or []:
        for part in tier.get("components") or []:
            if part.get("compensationType") == "Salary" and part.get("currencyCode") == "GBP" and part.get("interval") in {"1 YEAR", "YEAR", "ANNUAL"}:
                return amount_gbp(part.get("minValue")), amount_gbp(part.get("maxValue"))
    for part in comp.get("summaryComponents") or []:
        if part.get("compensationType") == "Salary" and part.get("currencyCode") == "GBP" and part.get("interval") in {"1 YEAR", "YEAR", "ANNUAL"}:
            return amount_gbp(part.get("minValue")), amount_gbp(part.get("maxValue"))
    return None, None


def salary_from_lever(job: dict) -> tuple[int | None, int | None]:
    sr = job.get("salaryRange") or {}
    currency = str(sr.get("currency", "")).upper()
    interval = str(sr.get("interval", "")).lower()
    if currency == "GBP" and interval in {"year", "yearly", "annual", "per-year", "per year"}:
        return amount_gbp(sr.get("min")), amount_gbp(sr.get("max"))
    return None, None


def normalized(company: str, provider: str, board: str, item: dict) -> dict | None:
    """Return common job fields or None for invalid/unlisted results."""
    if provider == "greenhouse":
        url = valid_job_link(item.get("absolute_url"))
        title = item.get("title")
        if not url or not title:
            return None
        # Greenhouse updated_at is NOT assumed to be initial posting date.
        desc = plain(item.get("content", ""))
        loc = str((item.get("location") or {}).get("name") or "")
        return {"id": f"greenhouse:{board}:{item.get('id')}", "title": str(title), "company": company,
                "location": loc, "url": url, "date": None, "description": desc,
                "workplace_type": "unknown", "salary_min": None, "salary_max": None, "source": provider}
    if provider == "lever":
        url = valid_job_link(item.get("hostedUrl"))
        title = item.get("text")
        if not url or not title:
            return None
        cats = item.get("categories") or {}
        locs = cats.get("allLocations") or []
        location = " / ".join(map(str, locs)) if locs else str(cats.get("location") or "")
        desc = plain(item.get("descriptionPlain") or item.get("description") or "")
        a, b = salary_from_lever(item)
        return {"id": f"lever:{board}:{item.get('id')}", "title": str(title), "company": company,
                "location": location, "url": url, "date": iso_date(item.get("createdAt")), "description": desc,
                "workplace_type": str(item.get("workplaceType") or "unknown").lower(),
                "salary_min": a, "salary_max": b, "source": provider}
    if provider == "ashby":
        if item.get("isListed") is False:
            return None
        url = valid_job_link(item.get("jobUrl"))
        title = item.get("title")
        if not url or not title:
            return None
        extra = [x.get("location") for x in item.get("secondaryLocations", []) if isinstance(x, dict) and x.get("location")]
        loc = " / ".join([str(item.get("location") or "")] + [str(x) for x in extra])
        a, b = salary_from_ashby(item)
        workplace = "remote" if item.get("isRemote") is True else str(item.get("workplaceType") or "unknown").lower()
        desc = plain(item.get("descriptionPlain") or item.get("descriptionHtml") or item.get("description") or "")
        return {"id": f"ashby:{board}:{item.get('id') or url.rsplit('/', 1)[-1]}", "title": str(title), "company": company,
                "location": loc, "url": url, "date": iso_date(item.get("publishedAt")), "description": desc,
                "workplace_type": workplace, "salary_min": a, "salary_max": b, "source": provider}
    raise ValueError(f"Unsupported provider: {provider}")


def endpoint(provider: str, board: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", board):
        raise ValueError("Unsafe board identifier")
    safe = quote(board, safe="")
    lookup = {
        "greenhouse": f"https://boards-api.greenhouse.io/v1/boards/{safe}/jobs?content=true",
        "lever": f"https://api.lever.co/v0/postings/{safe}?mode=json",
        "ashby": f"https://api.ashbyhq.com/posting-api/job-board/{safe}?includeCompensation=true",
    }
    if provider not in lookup:
        raise ValueError(f"Unknown provider {provider}")
    return lookup[provider]


def fetch_feed(company_source: dict, timeout: int = 15) -> list[dict]:
    provider = company_source["provider"]
    if provider == "smartrecruiters":
        from .extra_providers import fetch_smartrecruiters
        return fetch_smartrecruiters(company_source)
    if provider == "reed":
        from .extra_providers import fetch_reed
        return fetch_reed(company_source)
    if provider == "adzuna":
        from .extra_providers import fetch_adzuna
        return fetch_adzuna(company_source)
    if provider == "website":
        from .website import fetch_website_feed
        return fetch_website_feed(company_source)
    return fetch_snapshot(company_source, timeout=timeout)[0]


def fetch_snapshot(company_source: dict, validators=None, timeout=15):
    """Conditional GET for single-response ATS feeds; 304 preserves the snapshot."""
    provider = company_source["provider"]
    board = company_source["board"]
    headers = {"Accept": "application/json", "User-Agent": "UKJobHunterOpenSource/0.6"}
    for key, header in (("etag", "If-None-Match"), ("last_modified", "If-Modified-Since")):
        value = (validators or {}).get(key)
        if isinstance(value, str) and len(value) < 500 and not any(c in value for c in "\r\n"):
            headers[header] = value
    request = Request(endpoint(provider, board), headers=headers, method="GET")
    from urllib.request import build_opener, HTTPRedirectHandler
    class NoRedirect(HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None
    opener = build_opener(NoRedirect())
    try:
        with opener.open(request, timeout=timeout) as response:
            if response.geturl() != request.full_url:
                raise ValueError("Unexpected redirect")
            raw = response.read(10_000_001)
            response_headers = getattr(response, 'headers', {})
            new_validators = {k: response_headers[h] for k, h in
                              (("etag", "ETag"), ("last_modified", "Last-Modified"))
                              if isinstance(response_headers.get(h), str)}
    except HTTPError as exc:
        if exc.code == 304 and validators:
            return [], validators, True
        raise RuntimeError("ATS request failed (HTTP " + str(exc.code) + ")") from None
    except (URLError, TimeoutError):
        raise RuntimeError("ATS request failed; check access and network") from None
    if len(raw) > 10_000_000:
        raise RuntimeError("ATS feed exceeds 10 MB safety limit")
    try:
        obj = json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        raise RuntimeError("ATS returned invalid JSON") from None
    items = obj if provider == "lever" else obj.get("jobs") if isinstance(obj, dict) else None
    if not isinstance(items, list):
        raise RuntimeError("ATS returned unexpected feed schema")
    results = []
    for item in items:
        if not isinstance(item, dict):
            raise RuntimeError("ATS returned malformed posting")
        record = normalized(company_source["name"], provider, board, item)
        if record:
            if provider == 'ashby':
                address = (item.get('address') or {}).get('postalAddress') or {}
                countries = [str(address.get('addressCountry') or '')]
                countries += [str(((x.get('address') or {}).get('postalAddress') or x.get('address') or {}).get('addressCountry') or '')
                              for x in item.get('secondaryLocations', []) if isinstance(x, dict)]
                # Any explicit UK location is sufficient; multiple overseas
                # countries must not erase a UK secondary location.
                record['country'] = 'GB' if any(c.casefold() in {'gb', 'gbr', 'uk', 'united kingdom'} for c in countries) else next((c for c in countries if c), None)
                record['occupation'] = item.get('department') or None
                record['source_metadata'] = {'department': item.get('department'), 'employment_type': item.get('employmentType')}
            elif provider == 'lever':
                record['country'] = item.get('country') or None
                record['occupation'] = (item.get('categories') or {}).get('team') or None
            results.append(record)
    return results, new_validators, False
