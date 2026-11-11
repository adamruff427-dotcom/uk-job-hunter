"""Opt-in website-to-API adapter for public, structured career pages.

Reads schema.org/JobPosting JSON-LD from a configured careers page and a
small number of same-origin job detail links. No login, evasion, general web
crawler, external redirect following, or arbitrary LLM browsing.

Not a general-purpose hosted crawler: for a public multi-user deployment,
website sources must be approved and network isolation strengthened.
"""
from __future__ import annotations

from datetime import date
import hashlib
from html.parser import HTMLParser
import ipaddress
import json
import re
import socket
import time
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from urllib.robotparser import RobotFileParser

from .providers import plain, valid_job_link, iso_date, amount_gbp

USER_AGENT = "UKJobHunter-WebsiteAdapter/0.3 (+contact project maintainers via GitHub)"
MAX_HTML_BYTES = 1_500_000


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _hostname(url: str) -> str:
    parts = urlsplit(url)
    if parts.scheme != "https" or not parts.hostname or parts.username or parts.password or parts.port is not None or parts.fragment:
        raise ValueError("Website sources must use an HTTPS URL without credentials, custom port or fragment")
    host = parts.hostname.casefold()
    if host in {"localhost", "0.0.0.0"} or host.endswith((".localhost", ".local", ".internal", ".test")):
        raise ValueError("Local and internal hosts are not valid website sources")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        if "." not in host or not re.fullmatch(r"[a-z0-9.-]+", host) or ".." in host:
            raise ValueError("Invalid public website hostname")
    else:
        raise ValueError("IP-address hosts are not supported")
    return host


def verify_public_dns(host: str) -> None:
    """Fail closed on DNS results involving loopback, private or reserved IPs."""
    try:
        answers = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise RuntimeError(f"Website DNS resolution failed: {exc}") from exc
    if not answers:
        raise RuntimeError("Website DNS has no addresses")
    for result in answers:
        addr = result[4][0]
        if not ipaddress.ip_address(addr).is_global:
            raise RuntimeError("Website resolves to a non-public network address")


def validate_source(source: dict) -> tuple[str, tuple[str, ...], int]:
    raw_url = source.get("url")
    if not isinstance(raw_url, str):
        raise ValueError("A website source requires a careers URL")
    host = _hostname(raw_url)
    parts = urlsplit(raw_url)
    if not parts.path.startswith("/") or "\\" in parts.path:
        raise ValueError("Invalid careers path")
    prefixes = source.get("job_path_prefixes")
    if not isinstance(prefixes, list) or not prefixes or len(prefixes) > 10:
        raise ValueError("Website sources require explicit job_path_prefixes")
    for prefix in prefixes:
        if not isinstance(prefix, str) or prefix == "/" or not prefix.startswith("/") or ".." in prefix or "\\" in prefix or len(prefix) > 180:
            raise ValueError("Unsafe job path prefix")
    maximum = source.get("max_details", 10)
    if type(maximum) is not int or not 1 <= maximum <= 20:
        raise ValueError("max_details must be between 1 and 20")
    return host, tuple(prefixes), maximum


def _safe_page_link(base_url: str, ref: str, host: str, prefixes: tuple[str, ...]) -> str | None:
    if not isinstance(ref, str) or ref.startswith(("//", "javascript:", "data:")):
        return None
    url = urljoin(base_url, ref)
    parts = urlsplit(url)
    if parts.hostname != host or parts.port is not None or parts.username or parts.password:
        return None
    if not valid_job_link(url) or not any(parts.path.startswith(prefix) for prefix in prefixes):
        return None
    return urlunsplit((parts.scheme, parts.netloc, parts.path, parts.query, ""))


class JobPageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.in_ld = False
        self.ld_parts: list[str] = []
        self.ld_blocks: list[str] = []
        self.links: list[str] = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "script" and attrs.get("type", "").lower().split(";")[0].strip() == "application/ld+json":
            self.in_ld = True
            self.ld_parts = []
        elif tag == "a" and attrs.get("href"):
            self.links.append(attrs["href"])

    def handle_data(self, data):
        if self.in_ld:
            self.ld_parts.append(data)

    def handle_endtag(self, tag):
        if tag == "script" and self.in_ld:
            self.ld_blocks.append("".join(self.ld_parts))
            self.in_ld = False
            self.ld_parts = []


def _job_nodes(value: Any):
    if isinstance(value, list):
        for v in value:
            yield from _job_nodes(v)
    if isinstance(value, dict):
        kinds = value.get("@type", "")
        if isinstance(kinds, str):
            kinds = [kinds]
        if any(str(x).rsplit("/", 1)[-1] == "JobPosting" for x in kinds):
            yield value
        for key in ("@graph", "itemListElement", "item"):
            if key in value:
                yield from _job_nodes(value[key])


def _salary_gbp(item: dict) -> tuple[int | None, int | None]:
    amount = item.get("baseSalary")
    if not isinstance(amount, dict) or str(amount.get("currency", "")).upper() != "GBP":
        return None, None
    val = amount.get("value")
    if isinstance(val, (int, float)):
        if str(amount.get("unitText") or "").upper() not in {"YEAR", "ANNUAL", "YEARLY", "1 YEAR"}:
            return None, None
        return amount_gbp(val), amount_gbp(val)
    if not isinstance(val, dict):
        return None, None
    interval = str(val.get("unitText") or "").upper()
    if interval not in {"YEAR", "ANNUAL", "YEARLY", "1 YEAR"}:
        return None, None
    val_exact = amount_gbp(val.get("value"))
    return val_exact or amount_gbp(val.get("minValue")), val_exact or amount_gbp(val.get("maxValue"))


def _location(node: dict) -> str:
    kind = str(node.get("jobLocationType") or "").upper()
    locations = node.get("jobLocation") or []
    if not isinstance(locations, list):
        locations = [locations]
    parts = []
    for obj in locations:
        if not isinstance(obj, dict):
            continue
        addr = obj.get("address") or {}
        if isinstance(addr, dict):
            value = ", ".join(str(addr[k]) for k in ("addressLocality", "addressRegion", "addressCountry") if addr.get(k))
            if value:
                parts.append(value)
        elif isinstance(addr, str):
            parts.append(addr)
    if kind == "TELECOMMUTE":
        territories = node.get("applicantLocationRequirements") or []
        if not isinstance(territories, list):
            territories = [territories]
        for area in territories:
            if isinstance(area, dict):
                name = area.get("name")
                if name:
                    parts.append(str(name))
        return "Remote" + (" — " + ", ".join(parts) if parts else " (eligibility unknown)")
    return "; ".join(parts)


def extract_jobposting(html_page: str, page_url: str, source: dict) -> list[dict]:
    parser = JobPageParser()
    parser.feed(html_page)
    jobs = []
    for block in parser.ld_blocks:
        try:
            parsed = json.loads(block)
        except (json.JSONDecodeError, ValueError):
            continue
        for node in _job_nodes(parsed):
            title = node.get("title")
            if not isinstance(title, str) or not title.strip():
                continue
            valid_to = iso_date(node.get("validThrough"))
            if valid_to and valid_to < date.today().isoformat():
                continue
            salary_min, salary_max = _salary_gbp(node)
            location = _location(node)
            workplace = "remote" if str(node.get("jobLocationType", "")).upper() == "TELECOMMUTE" else "unknown"
            description = plain(node.get("description"))
            identifier = hashlib.sha256((page_url + "\0" + title).encode()).hexdigest()[:24]
            employer = node.get("hiringOrganization")
            company = str(employer.get("name") or source["name"]) if isinstance(employer, dict) else source["name"]
            jobs.append({"id": "website:" + identifier, "title": title.strip(), "company": company,
                         "location": location, "url": page_url, "date": iso_date(node.get("datePosted")),
                         "description": description, "workplace_type": workplace,
                         "salary_min": salary_min, "salary_max": salary_max, "source": "website",
                         "expires_at": valid_to, "occupation": node.get("occupationalCategory")})
    return jobs


def fetch_html(url: str, *, host: str, timeout: float = 12) -> str:
    if _hostname(url) != host:
        raise ValueError("Website request would leave the configured domain")
    verify_public_dns(host)
    req = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html"}, method="GET")
    opener = build_opener(NoRedirect())
    try:
        with opener.open(req, timeout=timeout) as r:
            if r.geturl() != url:
                raise RuntimeError("Website redirected unexpectedly")
            content_type = r.headers.get("Content-Type", "").lower()
            if "text/html" not in content_type:
                raise RuntimeError("Careers page is not HTML")
            data = r.read(MAX_HTML_BYTES + 1)
    except (HTTPError, URLError, TimeoutError) as exc:
        raise RuntimeError(f"Careers page could not be read ({type(exc).__name__})") from exc
    if len(data) > MAX_HTML_BYTES:
        raise RuntimeError("Careers page exceeds size limit")
    return data.decode("utf-8", errors="replace")


def allowed_by_robots(url: str, *, host: str) -> bool:
    robot_url = f"https://{host}/robots.txt"
    verify_public_dns(host)
    req = Request(robot_url, headers={"User-Agent": USER_AGENT}, method="GET")
    try:
        with build_opener(NoRedirect()).open(req, timeout=10) as r:
            data = r.read(128_001)
            if len(data) > 128_000:
                return False
    except HTTPError as exc:
        return exc.code in {404, 410}
    except (URLError, TimeoutError):
        return False
    robots = RobotFileParser(robot_url)
    robots.parse(data.decode("utf-8", errors="replace").splitlines())
    return robots.can_fetch(USER_AGENT, url)


def fetch_website_feed(source: dict, *, fetcher: Callable | None = None, robots_checker: Callable | None = None,
                       pause: Callable[[float], None] = time.sleep) -> list[dict]:
    """Convert opt-in career pages to our normalized job API representation.

    `fetcher` and `robots_checker` are injectable for unit tests; the network path
    otherwise enforces HTTPS, same-host URLs, DNS checks, redirect blocking and robots.
    """
    host, prefixes, limit = validate_source(source)
    getter = fetcher or (lambda u: fetch_html(u, host=host))
    can_fetch = robots_checker or (lambda u: allowed_by_robots(u, host=host))
    base = source["url"]
    if not can_fetch(base):
        raise RuntimeError(f"{source['name']}: robots.txt does not permit this careers page")
    listing = getter(base)
    results = extract_jobposting(listing, base, source)
    parser = JobPageParser()
    parser.feed(listing)
    urls = []
    seen_urls = {base}
    for link in parser.links:
        page = _safe_page_link(base, link, host, prefixes)
        if page and page not in seen_urls:
            urls.append(page)
            seen_urls.add(page)
        if len(urls) >= limit:
            break
    for url in urls:
        if not can_fetch(url):
            continue
        pause(0.8)
        try:
            results.extend(extract_jobposting(getter(url), url, source))
        except (RuntimeError, ValueError):
            continue
    unique = {j["id"]: j for j in results}
    if not unique:
        raise RuntimeError(f"{source['name']}: no structured JobPosting records found (page might require JavaScript or a site-specific adapter)")
    return list(unique.values())
