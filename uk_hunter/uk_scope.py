"""Only exclude vacancies with an explicitly non-UK-only location.

Unknown locations remain reviewable, *not* confirmed as UK eligible. This is
intentionally conservative; it cannot replace checking the employer advert.
"""
from __future__ import annotations

import re

UK = re.compile(r"\b(?:uk|gb|united kingdom|great britain|england|scotland|wales|northern ireland)\b", re.I)
NON_UK = re.compile(
    r"\b(?:united states|usa|u\.?s\.?a?\.?|canada|australia|new zealand|"
    r"germany|france|spain|italy|netherlands|belgium|switzerland|sweden|"
    r"norway|denmark|finland|poland|ireland|dublin|india|pakistan|"
    r"singapore|china|japan|hong kong|philippines|brazil|mexico|"
    r"south africa|nigeria|united arab emirates|uae|berlin|paris|toronto|"
    r"san francisco|new york|sydney|melbourne|amsterdam|barcelona|"
    r"copenhagen|oslo|delhi|bengaluru|mumbai)\b", re.I)


def has_uk_location(location: str) -> bool:
    # Overseas regions must not count as UK nations. Preserve mixed-country
    # postings with a separate explicit UK location.
    cleaned = re.sub(r'\b(?:new\s+south\s+wales|new\s+england|lake\s+wales)\b', '', location, flags=re.I)
    return bool(UK.search(cleaned))


def obviously_non_uk(location: str) -> bool:
    """False for unknown or multi-country listings mentioning the UK."""
    if not isinstance(location, str) or not location.strip():
        return False
    return bool(NON_UK.search(location)) and not has_uk_location(location)
