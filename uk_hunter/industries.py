"""Conservative, public-facing UK employer-industry classification.

Industry describes the employer's business, NOT a person's occupation. A risk
manager in a bank belongs to Financial Services. The source's declared sector
is preferred; otherwise the vacancy is explicitly unclassified unless its own
industry field or exceptionally strong posting clues establish the sector.
"""
from __future__ import annotations

import re
from typing import Any

INDUSTRIES = (
    ("financial-services", "Financial services"),
    ("technology", "Technology & digital"),
    ("defence-security", "Defence & security"),
    ("energy-utilities", "Energy & utilities"),
    ("healthcare", "Healthcare & life sciences"),
    ("public-sector", "Public sector"),
    ("education", "Education & research"),
    ("professional-services", "Professional services"),
    ("engineering-manufacturing", "Engineering & manufacturing"),
    ("transport-logistics", "Transport & logistics"),
    ("construction-property", "Construction & property"),
    ("retail-consumer", "Retail & consumer"),
    ("hospitality-leisure", "Hospitality & leisure"),
    ("charities", "Charities & not-for-profit"),
    ("unclassified", "Unclassified"),
)
LABELS = dict(INDUSTRIES)

ALIASES = {
    "financial-services": ("bank", "banking", "financial services", "finance", "fintech", "financial technology", "payments", "insurance", "insurtech", "wealth management", "investment", "credit union"),
    "technology": ("technology", "software", "saas", "it services", "cybersecurity", "cloud computing", "digital technology", "tech"),
    "defence-security": ("defence", "defense", "defence technology", "aerospace defence", "military", "national security", "physical security", "security services"),
    "energy-utilities": ("energy", "utilities", "electricity", "gas utility", "renewable", "renewables", "oil and gas", "water utility", "nuclear power"),
    "healthcare": ("healthcare", "health", "hospital", "nhs", "pharma", "pharmaceutical", "life sciences", "biotech", "medical devices", "social care"),
    "public-sector": ("public sector", "government", "civil service", "local authority", "local government", "council", "policing", "emergency services"),
    "education": ("education", "university", "higher education", "school", "college", "research institute", "academic"),
    "professional-services": ("professional services", "consultancy", "consulting", "legal services", "law firm", "accountancy", "audit firm"),
    "engineering-manufacturing": ("engineering", "manufacturing", "automotive", "industrial", "mechanical manufacturing", "electronics manufacturing"),
    "transport-logistics": ("transport", "logistics", "supply chain", "aviation", "airlines", "airport", "rail", "shipping", "freight"),
    "construction-property": ("construction", "property", "real estate", "housebuilding", "built environment", "facilities management"),
    "retail-consumer": ("retail", "consumer goods", "supermarket", "ecommerce", "e-commerce", "fmcg", "fashion"),
    "hospitality-leisure": ("hospitality", "leisure", "hotels", "restaurant", "tourism", "travel", "entertainment"),
    "charities": ("charity", "charities", "nonprofit", "not for profit", "not-for-profit", "third sector", "voluntary sector"),
}

# Strong organisation / industry references only; not generic role words like
# 'security', 'engineering', 'teacher', 'finance', 'risk' or 'operations'.
POSTING_CLUES = {
    "healthcare": (r"\bNHS (?:trust|foundation trust)\b", r"\bhealthcare provider\b"),
    "education": (r"\buniversity of [a-z -]+\b", r"\bfurther education college\b"),
    "public-sector": (r"\b(?:borough|county|city) council\b", r"\bcentral government department\b"),
    "defence-security": (r"\bdefence contractor\b", r"\barmed forces supplier\b"),
    "energy-utilities": (r"\benergy supplier\b", r"\belectricity network operator\b"),
    "financial-services": (r"\bregulated (?:bank|lender|insurer)\b", r"\bretail bank\b"),
    "transport-logistics": (r"\b(?:rail|airport) operator\b",),
}


def _by_label(raw: Any) -> str | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    value = re.sub(r"[\s_\-]+", " ", raw.casefold().strip())
    for key, label in INDUSTRIES:
        if value in {key.replace("-", " "), label.casefold().replace("&", "and").strip()}:
            return key
    if value in {"unspecified", "other", "unknown", "multi sector", "multi industry", "mixed", "none"}:
        return None
    # Prefer exact sector phrases (defence technology -> defence) before
    # shorter embedded keywords (technology -> technology).
    for key, terms in ALIASES.items():
        if value in terms:
            return key
    for key, terms in ALIASES.items():
        if any(len(term) > 5 and re.search(r"(?<!\w)" + re.escape(term) + r"(?!\w)", value) for term in terms):
            return key
    return None


def classify(job: dict, source_sector: Any = None) -> tuple[str, str]:
    """Return (canonical category, basis) without claiming unknown sectors.

    A curated employer-source classification wins where available. Multi-sector
    sources such as licensed job aggregators defer to explicit job metadata.
    """
    explicit = _by_label(source_sector)
    if explicit:
        return explicit, "employer"
    explicit = _by_label(job.get("industry") or job.get("sector"))
    if explicit:
        return explicit, "posting"
    text = " ".join(str(job.get(k) or "") for k in ("company", "description"))[:6000]
    matches = [key for key, patterns in POSTING_CLUES.items() if any(re.search(p, text, re.I) for p in patterns)]
    if len(matches) == 1:
        return matches[0], "inferred"
    return "unclassified", "unknown"


def industry_counts(jobs: list[dict]) -> list[dict]:
    counts = {key: {"count": 0, "matched": 0} for key, _ in INDUSTRIES}
    for job in jobs:
        key = job.get("industry")
        if key not in counts:
            key = "unclassified"
        counts[key]["count"] += 1
        if job.get("verdict") in {"SHORTLIST", "REVIEW"}:
            counts[key]["matched"] += 1
    return [{"id": key, "label": label, **counts[key]} for key, label in INDUSTRIES]
