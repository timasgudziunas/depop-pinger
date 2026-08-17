"""Filters normalized listings against config criteria (keywords, exclusion
terms, size, price, condition, country, kids).

Pure functions: data in, bool out, no I/O.
"""

import logging
import re

import config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Sentinel to distinguish "caller didn't pass this kwarg" (use config default)
# from "caller explicitly passed None" (e.g. max_price=None means no ceiling,
# which is also config's own default -- so a plain `None` default wouldn't be
# able to tell the two cases apart).
_UNSET = object()

_CURLY_QUOTES = {
    "’": "'",
    "‘": "'",
    "“": '"',
    "”": '"',
}


def _normalize_text(text: str) -> str:
    """Casefold, straighten curly quotes, turn hyphens into spaces, and
    collapse whitespace runs to a single space. Used for both required-
    keyword and excluded-term matching so "speed-up" / "high-rise" match the
    same as their spaced-out equivalents."""
    normalized = text.casefold()
    for curly, straight in _CURLY_QUOTES.items():
        normalized = normalized.replace(curly, straight)
    normalized = normalized.replace("-", " ").replace("–", " ")
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def matches_criteria(
    listing: dict,
    required_keywords: list[str] = _UNSET,
    excluded_terms: list[str] = _UNSET,
    target_sizes: list[str] = _UNSET,
    max_price: float | None = _UNSET,
    allowed_conditions: list[str] = _UNSET,
    allowed_countries: list[str] = _UNSET,
) -> bool:
    """Return True if listing passes every configured criterion.

    All params default to the corresponding config.* constant but can be
    overridden (e.g. in tests) without touching config.py.
    """
    if required_keywords is _UNSET:
        required_keywords = config.REQUIRED_KEYWORDS
    if excluded_terms is _UNSET:
        excluded_terms = config.EXCLUDED_TERMS
    if target_sizes is _UNSET:
        target_sizes = config.TARGET_SIZES
    if max_price is _UNSET:
        max_price = config.MAX_PRICE
    if allowed_conditions is _UNSET:
        allowed_conditions = config.ALLOWED_CONDITIONS
    if allowed_countries is _UNSET:
        allowed_countries = config.ALLOWED_COUNTRIES

    return (
        _matches_required_keywords(listing, required_keywords)
        and _has_no_excluded_term(listing, excluded_terms)
        and _matches_size(listing, target_sizes)
        and _matches_price(listing, max_price)
        and _matches_condition(listing, allowed_conditions)
        and _matches_country(listing, allowed_countries)
        and _is_not_kids(listing)
    )


def _matches_required_keywords(listing: dict, required_keywords: list[str]) -> bool:
    """Skipped entirely if required_keywords is empty. Otherwise the
    (normalized) title must contain at least one (normalized) keyword as a
    substring."""
    if not required_keywords:
        return True
    title = _normalize_text(listing.get("title") or "")
    return any(_normalize_text(keyword) in title for keyword in required_keywords)


def _has_no_excluded_term(listing: dict, excluded_terms: list[str]) -> bool:
    """Skipped entirely if excluded_terms is empty. Otherwise the listing
    fails if any excluded term appears as a whole word/phrase (word-boundary
    match) in the normalized title."""
    if not excluded_terms:
        return True
    title = _normalize_text(listing.get("title") or "")
    for term in excluded_terms:
        pattern = r"(?<!\w)" + re.escape(_normalize_text(term)) + r"(?!\w)"
        if re.search(pattern, title):
            return False
    return True


def _matches_size(listing: dict, target_sizes: list[str]) -> bool:
    """Case-insensitive size match; skipped entirely if target_sizes is empty."""
    if not target_sizes:
        return True
    size = listing.get("size")
    if size is None:
        # A listing with no parsed size is treated as NOT matching once sizes
        # are specified: better to miss an ambiguous listing than spam on a
        # size that might be wrong. Flip this to `return True` if under-firing
        # turns out worse than over-firing in practice.
        return False
    size_normalized = size.strip().casefold()
    return any(size_normalized == target.strip().casefold() for target in target_sizes)


def _matches_price(listing: dict, max_price: float | None) -> bool:
    """Price ceiling check; skipped entirely if max_price is None."""
    if max_price is None:
        return True
    return listing["price"] <= max_price


def _matches_condition(listing: dict, allowed_conditions: list[str]) -> bool:
    """Skipped if allowed_conditions is empty OR the listing's condition is
    missing/None -- filter only on positive evidence."""
    if not allowed_conditions:
        return True
    condition = listing.get("condition")
    if condition is None:
        return True
    condition_normalized = condition.strip().casefold()
    return any(
        condition_normalized == allowed.strip().casefold() for allowed in allowed_conditions
    )


def _matches_country(listing: dict, allowed_countries: list[str]) -> bool:
    """Skipped if allowed_countries is empty OR the listing's country is
    missing/None -- filter only on positive evidence."""
    if not allowed_countries:
        return True
    country = listing.get("country")
    if country is None:
        return True
    country_normalized = country.strip().casefold()
    return any(
        country_normalized == allowed.strip().casefold() for allowed in allowed_countries
    )


def _is_not_kids(listing: dict) -> bool:
    """Kids listings are never wanted, regardless of config -- no knob."""
    return listing.get("is_kids") is not True
