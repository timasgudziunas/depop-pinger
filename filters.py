"""Filters normalized listings against config criteria (size, price).

Pure functions: data in, bool out, no I/O.
"""

import logging

import config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Sentinel to distinguish "caller didn't pass this kwarg" (use config default)
# from "caller explicitly passed None" (e.g. max_price=None means no ceiling,
# which is also config's own default -- so a plain `None` default wouldn't be
# able to tell the two cases apart).
_UNSET = object()


def matches_criteria(
    listing: dict,
    target_sizes: list[str] = _UNSET,
    max_price: float | None = _UNSET,
) -> bool:
    """Return True if listing passes size and price criteria.

    target_sizes and max_price default to config.TARGET_SIZES /
    config.MAX_PRICE but can be overridden (e.g. in tests) without touching
    config.py.
    """
    if target_sizes is _UNSET:
        target_sizes = config.TARGET_SIZES
    if max_price is _UNSET:
        max_price = config.MAX_PRICE
    return _matches_size(listing, target_sizes) and _matches_price(listing, max_price)


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
