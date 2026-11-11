"""Conservative, explainable fit filters. Not an LLM fit assessment."""
from __future__ import annotations

from datetime import date, timedelta
import re
from typing import Any


def annual_salary_from_text(description: str) -> tuple[int | None, int | None]:
    """Extract only clearly labelled annual GBP base salary bands.

    Conservative on purpose: unknown compensation is marked for review, not
    quietly converted to a false £50k match. Never use OTE or commission as base.
    """
    lines = description.splitlines()
    for line in lines:
        s = line.strip().lower()
        if not re.search(r"\b(base salary|basic salary|salary range|annual salary|salary|remuneration)\b", s):
            continue
        if re.search(r"\b(ote|on.target earnings|commission|bonus only)\b", s):
            continue
        if "£" not in s or len(s) > 250:
            continue
        amounts = []
        for raw, suffix in re.findall(r"£\s*([\d,]+(?:\.\d+)?)\s*([kK]?)", s):
            value = float(raw.replace(",", ""))
            if suffix:
                value *= 1000
            if value >= 15000:
                amounts.append(int(value))
        if not amounts:
            continue
        if not re.search(r"\b(annum|per year|a year|yearly|annual|salary|pa|p\.a\.)\b", s):
            continue
        if len(amounts) >= 2:
            return min(amounts[:2]), max(amounts[:2])
        if re.search(r"\b(up to|maximum|max)\b", s):
            return None, amounts[0]
        if re.search(r"\b(from|starting at|minimum|min)\b", s):
            return amounts[0], None
        # A lone salary figure is a point offer, not a guaranteed minimum;
        # preserve as both ends for review.
        return amounts[0], amounts[0]
    return None, None


def _matches_place(location: str, place: str) -> bool:
    """Avoid partial matches such as Bath in Bathgate or York in New York."""
    place = place.strip().casefold()
    if not place:
        return False
    return re.search(r"(?<!\w)" + re.escape(place) + r"(?!\w)", location.casefold()) is not None


def loc_verdict(location: str, workplace: str, profile: dict) -> tuple[str, str]:
    """User-configurable UK location screening. Unknown commutes never hard-fail."""
    loc = (location or "").casefold()
    work = (workplace or "unknown").casefold()
    uk = bool(re.search(r"\b(uk|gb|united kingdom|great britain|britain)\b", loc))
    outside = re.search(
        r"\b(united states|usa|san francisco|new york|los angeles|seattle|"
        r"austin|california|toronto|canada|sydney|melbourne|barcelona|"
        r"dublin|spain|france|germany|india|singapore|eu only|european union)\b", loc
    )
    if outside and not uk:
        return "FAIL", "Listing appears restricted to a non-UK location"
    uk_remote = bool(re.search(
        r"remote\s*\((?:uk|gb)\)|remote\s+(?:within|across|in)\s+(?:the\s+)?(?:uk|united kingdom)|"
        r"(?:uk|united kingdom)\s+remote", loc
    ))
    if uk_remote or (work == "remote" and uk):
        return "PASS", "UK-remote indicated; independently confirm eligibility and office days"
    if work == "remote" or "remote" in loc:
        return "REVIEW", "Remote listing; eligibility to work from the UK not explicit"
    if any(_matches_place(loc, place) for place in profile.get("excluded_commute_places", [])):
        return "FAIL", "Location explicitly excluded by your commute configuration"
    if any(_matches_place(loc, place) for place in profile.get("nearby_places", [])):
        return "PASS", "Location matches an explicitly approved commute area; confirm office days"
    if any(_matches_place(loc, place) for place in profile.get("hybrid_review_places", [])):
        return "REVIEW", "Potential commute; office attendance needs checking"
    if outside and not uk:
        return "FAIL", "Listed location appears to be outside the UK"
    return "REVIEW", "On-site or hybrid viability not configured or not established"


def evaluate(job: dict, profile: dict, days: int | None = None, today: date | None = None) -> dict:
    job = dict(job)
    title = job["title"].lower().strip()
    reasons = []
    if days is not None and job.get("date"):
        try:
            if date.fromisoformat(job["date"]) < (today or date.today()) - timedelta(days=days):
                job.update(verdict="SKIP_OLD", score=0, reasons=[f"Posted more than {days} days ago"])
                return job
        except ValueError:
            reasons.append("Posting date malformed — needs verification")
    if any(x in title for x in profile.get("excluded_title_terms", [])):
        job.update(verdict="REJECT", score=0, reasons=["Role requires a specialist/senior track outside the current evidence-based targets"])
        return job

    exact = [x for x in profile.get("target_roles", []) if x in title]
    related = [x for x in profile.get("related_terms", []) if x in title]
    if not exact and not related:
        job.update(verdict="REJECT", score=0, reasons=["Job title does not demonstrate a credible experience match"])
        return job
    role_score = 60 if exact else 35
    reasons.append(f"Title match: {exact[0]}" if exact else f"Adjacent role: {related[0]} (manual evidence check required)")
    location_gate, location_note = loc_verdict(job.get("location") or "", job.get("workplace_type") or "", profile)
    job["location_gate"] = location_gate
    reasons.append(location_note)
    if location_gate == "FAIL":
        job.update(verdict="REJECT", score=0, reasons=reasons)
        return job

    lo = job.get("salary_min")
    hi = job.get("salary_max")
    if lo is None and hi is None:
        lo, hi = annual_salary_from_text(job.get("description") or "")
        job["salary_min"], job["salary_max"] = lo, hi
    floor = profile.get("minimum_basic_salary_gbp")
    if floor is not None and floor < 0:
        raise ValueError("minimum_basic_salary_gbp must be nonnegative or null")
    if floor is not None and hi is not None and hi < floor:
        job.update(verdict="REJECT", score=0, reasons=reasons + [f"Advertised upper salary £{hi:,} is below £{floor:,} base salary floor"])
        return job
    if floor is None:
        salary_gate = "PASS"
        reasons.append("No minimum base-salary threshold configured; verify advertised compensation")
    elif lo is None:
        salary_gate = "REVIEW"
        reasons.append("Base salary absent or minimum unconfirmed; do not assume threshold met")
    elif lo < floor:
        salary_gate = "REVIEW"
        reasons.append(f"Band begins at £{lo:,}, below £{floor:,}; request confirmed offer range")
    else:
        salary_gate = "PASS"
        reasons.append(f"Advertised annual base salary starts at £{lo:,}")
    job["salary_gate"] = salary_gate
    # Transparent triage score, not a probability of getting the job.
    score = role_score + (25 if location_gate == "PASS" else 7) + (15 if salary_gate == "PASS" else 0)
    verdict = "SHORTLIST" if exact and location_gate == "PASS" and salary_gate == "PASS" else "REVIEW"
    if not exact:
        reasons.append("Verify transferable experience against all essential requirements")
    if not job.get("date"):
        reasons.append("Publication date unverified (feed may expose update time only)")
    job.update(verdict=verdict, score=score, reasons=reasons)
    return job
