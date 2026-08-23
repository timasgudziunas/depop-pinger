"""Fetches current live Depop listings for a search query.

Data source (PLAN.md Phase 2, option 1): mimics a plain browser page load of
Depop's own search results page, exactly what depop.com does when a person
searches. There is no working public JSON search API to call directly —
`https://webapi.depop.com/api/v3/search/products/` (the historically known
endpoint) now returns HTTP 410 with `{"code":9001,"message":"Deprecated
endpoint", ...}`, verified empirically 2026-08-14. `https://www.depop.com/search/`
itself is NOT Cloudflare-challenged for plain `requests` calls with honest
browser-ish headers (verified empirically, ~20 live requests during
development, no 403/503 challenge pages seen except one isolated transient
403 that cleared on the next identical request).

Depop's search page is server-rendered with Next.js App Router. The listing
data isn't in a `<script type="application/json">` blob (no `__NEXT_DATA__`);
it's streamed as React Server Component (RSC) payload chunks via repeated
`self.__next_f.push([1,"<JS-escaped string>"])` calls in inline `<script>`
tags. Concatenating and JS-unescaping those chunks yields one large text
blob containing a dehydrated react-query cache, inside which is:

    {"objects": [ <product dict>, <product dict>, ... ],
     "meta": {"total_count": N},
     "page_info": {"has_more": bool, "last": "<pagination cursor>"}}

This module parses that blob with a small bracket-balancing scanner (regex
alone can't safely extract nested JSON) rather than calling a separate API
endpoint. This IS "mimicking the browser request" in spirit: it's the exact
HTML response depop.com's own frontend consumes to hydrate the page.

Fetch transport (CLAUDE.md "data source option 2", ScrapeBadger live as of
2026-08-23, replacing Bright Data Web Unlocker which was abandoned the same
day -- Bright Data compliance-blocks depop.com outright and their KYC path
is business-only, see CLAUDE.md): when `config.SCRAPER_API_KEY` is set,
listings are fetched via ScrapeBadger's dedicated Depop API
(`https://scrapebadger.com/v1/depop`) instead of scraping a rendered page at
all. This is a structurally different transport from the RSC-parsing path
below -- ScrapeBadger returns clean JSON (a `/search` card list, then a
`/products/{slug}` detail call per surviving candidate), not page HTML, so
none of the RSC extraction functions in this module apply to it. See the
`_fetch_listings_via_scrapebadger` docstring for the two-step design. When
`SCRAPER_API_KEY` is unset, the module falls back to the original direct
`requests.get` against depop.com and the RSC parsing below (works on
residential IPs only, e.g. local runs) -- that fallback path, and everything
below about the RSC payload shape, is otherwise unchanged.

The rest of this section (through "Gotchas") documents the direct/RSC
fallback path specifically -- ScrapeBadger's JSON shape is different and is
documented instead as code comments near `_normalize_scrapebadger_product`.

What the API exposes about SIZE (verified empirically): each product object
has a `sizes` array, e.g. `[{"name": "4", "id": 6, "quantity": 1,
"status": "STATUS_ONSALE", "variant": "4"}]`. In every listing observed
during development, `sizes` had exactly one entry (single-variant listings
are the norm on Depop; multi-size listings do exist but weren't seen in
sample data). We normalize `size` as the `name` of the first entry, or
`None` if the array is empty. There is no separate top-level "size" string
field.

What the API exposes about PRICE/CURRENCY: `pricing.currency` (e.g. "USD")
and `pricing.current_price.total_price` (item price + buyer fee + tax,
EXCLUDING shipping, which is broken out separately under
`pricing.current_price.price_breakdown.shipping`). We use `total_price` as
the normalized `price` since it's what Depop displays as the item's price.

What the API exposes about COUNTRY/CONDITION/KIDS (verified empirically
against tests/fixtures/search_response.json): each product object has a
top-level `country` string (e.g. "US") and an `attributes` object carrying
`attributes.condition` (enum values observed: `brand_new`,
`used_like_new`, `used_excellent`, `used_good`) and `attributes.is_kids`
(bool). Every fixture object had `attributes` populated, but it's guarded
with `.get(...) or {}` regardless since it isn't a field we've seen Depop
document or guarantee.

Gotchas:
  - No `title` field exists. Depop listings only have a free-text
    `description` (what sellers type, often including hashtags) — that IS
    what Depop's own search cards display as the title, so we use it as-is.
  - No timestamp/creation-date field is present anywhere in the search
    response, so newest-first ordering can't be verified by inspecting the
    payload directly. We pass `sort=newest` (documented third-party-reversed
    enum value, alongside `relevance` (default), `priceAscending`,
    `priceDescending`, `popularity`) on the request. Empirically,
    `sort=priceAscending` / `priceDescending` visibly changed result order
    (confirming the `sort` param IS honored), but `sort=newest` produced the
    same order as the unsorted default for our test queries — meaning we
    could not independently confirm `newest` re-orders results beyond what
    default relevance ranking already gives for small result sets. Treat
    ordering as best-effort, not guaranteed strict newest-first.
  - Pagination: the response is one "page" of listings (24 objects observed,
    matching Depop's default page size; there's no `itemsPerPage` URL param
    that changes this). `page_info.has_more` / `page_info.last` (an opaque
    cursor) exist for infinite-scroll pagination but this module does not
    follow them — fine for new-listing alerting, which only needs the most
    recent page.
  - No rate-limit headers were observed on any response.
  - If Depop's markup changes and the RSC blob or `objects` array can't be
    found, this raises `DepopResponseSchemaError` rather than silently
    returning an empty list, per this repo's "crash on schema errors" rule
    — an empty list would look identical to "no matching listings" and could
    silently break alerting.
"""

from __future__ import annotations

import json
import logging
import sys
import time

import requests

import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# --- Tunables -----------------------------------------------------------

SEARCH_URL = "https://www.depop.com/search/"
REQUEST_TIMEOUT_SECONDS = 15
# Best-effort "most recent first" sort value for the direct/RSC fallback
# path (see module docstring gotchas). Unrelated to SCRAPEBADGER_SORT_VALUE
# below -- same string value, different API.
SORT_VALUE = "newest"

# ScrapeBadger's dedicated Depop API (used instead of the direct/RSC path
# when config.SCRAPER_API_KEY is set). Live as of 2026-08-23, replacing
# Bright Data Web Unlocker (see CLAUDE.md and module docstring).
SCRAPEBADGER_BASE_URL = "https://scrapebadger.com/v1/depop"
SCRAPER_TIMEOUT_SECONDS = 20
# ScrapeBadger's docs claim the "newest first" sort value is "newlyListed",
# but that returns HTTP 502 (verified live 2026-08-23). "newest" is the
# value that actually works ("newly_listed" also works; "newest" is used
# here for readability). Flagging the docs/reality mismatch for whoever
# hits this next.
SCRAPEBADGER_SORT_VALUE = "newest"
# Free tier is 5 requests/minute. On 429, sleep until the response's
# reset_at (capped) and retry, up to this many times, before giving up.
MAX_429_RETRIES = 2
MAX_429_SLEEP_SECONDS = 90
# Plain, honest desktop-browser headers. No anti-bot spoofing.
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)
REQUEST_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

# RSC stream chunks look like: self.__next_f.push([1,"<js-escaped text>"])
_NEXT_CHUNK_PREFIX = 'self.__next_f.push([1,"'
_OBJECTS_KEY = '"objects":['


class DepopResponseSchemaError(Exception):
    """Raised when Depop's search response no longer matches the expected
    shape. This is a "the site changed, code needs updating" condition, not
    a transient failure, so callers should let it crash rather than
    swallowing it and silently alerting on nothing."""


def fetch_listings(query: str, skip_ids: set[str] | None = None) -> list[dict]:
    """Fetch current live Depop listings matching `query`.

    `skip_ids` is the set of listing ids (see tracker.py/state.py -- "already
    evaluated", not just "already alerted") to not bother re-fetching detail
    for -- callers should pass `set(state.load_seen())`.

    Returns a list of normalized dicts with keys: id (str), title (str),
    price (float), currency (str), size (str or None), url (str),
    image_url (str or None), country (str or None), condition (str or
    None), is_kids (bool or None). Returns an empty list on transient
    network errors (logged) or on a genuine zero-result search. Raises
    DepopResponseSchemaError if the response no longer matches the expected
    shape, or ValueError on a 401/403 (bad SCRAPER_API_KEY -- a config error,
    crash loudly).

    When config.SCRAPER_API_KEY is set, routes through ScrapeBadger's Depop
    API (see `_fetch_listings_via_scrapebadger`). Otherwise falls back to
    the direct/RSC path against depop.com (residential IPs only), best-
    effort newest-first per the module docstring.
    """
    if config.SCRAPER_API_KEY:
        listings = _fetch_listings_via_scrapebadger(query, skip_ids or set())
        logger.info("fetch_listings(%r) via ScrapeBadger: %d listings returned", query, len(listings))
        return listings

    html = _fetch_search_html_direct(query)
    if html is None:
        return []

    product_objects = _extract_product_objects(html)
    # The RSC payload can contain more than one product-shaped "objects"
    # array; dedupe by id (order-preserving) so one run never yields the
    # same listing twice.
    unique_by_id: dict[str, dict] = {}
    for obj in product_objects:
        unique_by_id.setdefault(str(obj["id"]), obj)
    listings = [
        _normalize_product(obj)
        for obj in unique_by_id.values()
        if str(obj["id"]) not in (skip_ids or set())
    ]
    logger.info("fetch_listings(%r) direct: %d listings returned", query, len(listings))
    return listings


def _fetch_search_html_direct(query: str) -> str | None:
    """GET the Depop search results page directly. Returns the HTML body,
    or None on a transient network error / non-recoverable HTTP status
    (logged)."""
    params = {"q": query, "sort": SORT_VALUE}
    try:
        response = requests.get(
            SEARCH_URL,
            params=params,
            headers=REQUEST_HEADERS,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        logger.warning("Depop search request failed (network error): %s", exc)
        return None

    if response.status_code != 200:
        challenge_markers = ("Just a moment", "Attention Required", "cf-challenge")
        if any(marker in response.text for marker in challenge_markers):
            logger.warning(
                "Depop search returned HTTP %d with what looks like a "
                "Cloudflare challenge page. Per this repo's hard boundary, "
                "not attempting to bypass it. Returning no listings.",
                response.status_code,
            )
        else:
            logger.warning(
                "Depop search returned unexpected HTTP %d (not a challenge "
                "page). Returning no listings.",
                response.status_code,
            )
        return None

    return response.text


def _fetch_listings_via_scrapebadger(query: str, skip_ids: set[str]) -> list[dict]:
    """Two-step ScrapeBadger fetch: a cheap search call returns lightweight
    "cards" (no id, no title/condition), then a per-listing detail call
    (same cost as search, 10 credits) fills in what's missing. Detail calls
    are the expensive/rate-limited part, so cards are prefiltered first
    (zero extra cost) on everything decidable from the card alone: sold,
    already-evaluated (skip_ids), wrong size, over price. Only surviving
    cards get a detail call, capped at config.MAX_DETAIL_FETCHES_PER_RUN.

    Returns [] on a search failure (logged). A listing whose detail fetch
    fails after retries is skipped (logged) and NOT returned, so it isn't
    marked seen by the caller and gets retried next run."""
    products = _scrapebadger_search(query)
    if products is None:
        return []

    survivors = [card for card in products if _card_survives_prefilter(card, skip_ids)]
    # Health signal: with prefiltering, 0 listings returned is the NORMAL
    # healthy outcome most runs -- the card count is what proves the search
    # actually fetched. This query never genuinely returns 0 cards (23-24
    # typical), so 0 cards on a 200 means something upstream broke silently.
    log = logger.warning if not products else logger.info
    log(
        "ScrapeBadger search for %r: %d cards returned, %d survived prefilter",
        query, len(products), len(survivors),
    )

    if len(survivors) > config.MAX_DETAIL_FETCHES_PER_RUN:
        dropped = len(survivors) - config.MAX_DETAIL_FETCHES_PER_RUN
        logger.warning(
            "%d cards survived prefiltering for %r but config.MAX_DETAIL_FETCHES_PER_RUN "
            "is %d -- dropping %d this run (they'll be reconsidered next run since "
            "they aren't marked seen without a detail fetch).",
            len(survivors), query, config.MAX_DETAIL_FETCHES_PER_RUN, dropped,
        )
        survivors = survivors[: config.MAX_DETAIL_FETCHES_PER_RUN]

    listings = []
    for card in survivors:
        detail = _scrapebadger_detail(card["slug"])
        if detail is None:
            logger.warning(
                "Detail fetch failed for slug=%s after retries; skipping this run "
                "(will retry next run).", card["slug"],
            )
            continue
        listings.append(_normalize_scrapebadger_product(card, detail))
    return listings


def _card_survives_prefilter(card: dict, skip_ids: set[str]) -> bool:
    """Zero-credit prefilter on a ScrapeBadger search card, before spending a
    detail call on it. Skip when: sold, already evaluated (skip_ids), wrong
    size (target_sizes set and no case-insensitive match -- a card with no
    size is skipped too, mirroring filters._matches_size's "no size = no
    match once sizes are configured" semantics), or over the price ceiling.
    """
    if card.get("is_sold"):
        return False
    if card.get("slug") in skip_ids:
        return False
    if config.TARGET_SIZES and not _card_size_matches(card.get("size"), config.TARGET_SIZES):
        return False
    if config.MAX_PRICE is not None and float(card["price"]) > config.MAX_PRICE:
        return False
    return True


def _card_size_matches(size: str | None, target_sizes: list[str]) -> bool:
    """Case-insensitive size match, mirroring filters._matches_size (kept as
    a separate copy here rather than importing that private helper, so the
    prefilter doesn't depend on filters.py's internals)."""
    if size is None:
        return False
    size_normalized = size.strip().casefold()
    return any(size_normalized == target.strip().casefold() for target in target_sizes)


def _scrapebadger_search(query: str) -> list[dict] | None:
    """GET {SCRAPEBADGER_BASE_URL}/search. Returns the "products" card list,
    or None on a transient failure (logged; caller returns no listings for
    this run). Raises DepopResponseSchemaError if a 200 response is missing
    the "products" key.

    Deliberately does NOT send ScrapeBadger's documented `sizes` filter
    param: verified live 2026-08-23 that `sizes=2` returned the identical
    mixed-size result set as no filter at all (no error, just silently
    ignored). Size narrowing therefore stays local-only, in
    `_card_survives_prefilter` / filters._matches_size. Do not re-add a
    `sizes` param here without re-verifying live first.

    Does send `price_max` (when config.MAX_PRICE is set): verified live
    2026-08-23 that with price_max=25 the API returned a full page of 24
    cards ALL priced at or under $25.00, so page 1 stops wasting slots on
    over-budget listings -- better coverage of relevant listings on a given
    page, with no change to the "N cards returned" health signal.
    """
    params = {"query": query, "market": config.MARKET, "sort": SCRAPEBADGER_SORT_VALUE}
    if config.MAX_PRICE is not None:
        params["price_max"] = config.MAX_PRICE
    response = _scrapebadger_get("/search", params)
    if response is None:
        return None
    if response.status_code != 200:
        logger.warning(
            "ScrapeBadger search returned unexpected HTTP %d. Returning no listings.",
            response.status_code,
        )
        return None
    data = response.json()
    if "products" not in data:
        raise DepopResponseSchemaError(
            'ScrapeBadger search response is missing the "products" key -- '
            "the API's response shape may have changed."
        )
    return data["products"]


def _scrapebadger_detail(slug: str) -> dict | None:
    """GET {SCRAPEBADGER_BASE_URL}/products/{slug}. Returns the parsed detail
    dict, or None on a transient failure (logged; caller skips this
    listing)."""
    response = _scrapebadger_get(f"/products/{slug}", {"market": config.MARKET})
    if response is None:
        return None
    if response.status_code != 200:
        logger.warning(
            "ScrapeBadger detail fetch for slug=%s returned unexpected HTTP %d.",
            slug, response.status_code,
        )
        return None
    return response.json()


def _scrapebadger_get(path: str, params: dict) -> "requests.Response | None":
    """GET {SCRAPEBADGER_BASE_URL}{path} with X-API-Key auth. Handles 429
    (free tier: 5 req/min) by sleeping until the response's `reset_at`
    (capped at MAX_429_SLEEP_SECONDS) and retrying, up to MAX_429_RETRIES
    times -- after that, the last response (still a 429) is returned as-is
    for the caller's normal non-200 handling. Raises ValueError on 401/403
    (bad SCRAPER_API_KEY -- a config error, crash loudly rather than
    silently return no listings forever). Returns None on
    requests.RequestException (network error, logged)."""
    url = f"{SCRAPEBADGER_BASE_URL}{path}"
    headers = {"X-API-Key": config.SCRAPER_API_KEY}
    attempt = 0
    while True:
        try:
            response = requests.get(url, params=params, headers=headers, timeout=SCRAPER_TIMEOUT_SECONDS)
        except requests.RequestException as exc:
            logger.warning("ScrapeBadger request to %s failed (network error): %s", path, exc)
            return None

        if response.status_code in (401, 403):
            raise ValueError(
                f"ScrapeBadger returned HTTP {response.status_code} on {path} -- "
                "likely a bad SCRAPER_API_KEY. This is a config error, not a "
                "transient one."
            )

        if response.status_code == 429 and attempt < MAX_429_RETRIES:
            attempt += 1
            try:
                reset_at = response.json().get("reset_at")
            except ValueError:
                reset_at = None
            sleep_seconds = MAX_429_SLEEP_SECONDS
            if reset_at is not None:
                sleep_seconds = min(max(reset_at - time.time(), 0), MAX_429_SLEEP_SECONDS)
            logger.warning(
                "ScrapeBadger rate limited (429) on %s, sleeping %.0fs then retrying "
                "(attempt %d/%d).", path, sleep_seconds, attempt, MAX_429_RETRIES,
            )
            time.sleep(sleep_seconds)
            continue

        return response


# ScrapeBadger condition values seen live, mapped to this module's existing
# condition vocabulary (config.ALLOWED_CONDITIONS / filters.py). Schema.org-
# style strings ("UsedCondition"), not the docs' claimed "Used - excellent"
# form. "UsedCondition" maps to None (passes the filter on the existing
# only-positive-evidence principle -- filters._matches_condition treats a
# missing condition as a pass) rather than to any of the used_* granularity
# levels, because ScrapeBadger doesn't expose anything finer than new/used.
# That granularity loss is accepted: the text dealbreakers (stains, pilling,
# etc. in config.EXCLUDED_TERMS) plus a human looking at photos before
# buying cover the gap.
_CONDITION_MAP = {
    "NewCondition": "brand_new",
    "UsedCondition": None,
}


def _map_condition(raw_condition: str | None) -> str | None:
    """Map a raw ScrapeBadger condition string to this module's normalized
    condition vocabulary. Unknown non-null values pass the filter (None) but
    are logged so the real enum can be learned over time."""
    if raw_condition is None:
        return None
    if raw_condition in _CONDITION_MAP:
        return _CONDITION_MAP[raw_condition]
    logger.warning(
        "Unrecognized ScrapeBadger condition value %r -- treating as unknown "
        "(passes the condition filter). Add it to _CONDITION_MAP once seen "
        "enough to know what it means.", raw_condition,
    )
    return None


def _normalize_scrapebadger_product(card: dict, detail: dict) -> dict:
    """Merge a ScrapeBadger search card and its detail response into this
    module's normalized listing shape (same keys _normalize_product
    produces, so filters.py needs no changes). `id` is the slug (a string)
    -- ScrapeBadger's search cards carry no numeric id at all, only detail
    does, so keying on slug avoids a second lookup just to get an id state
    can track. `size` and `image` only exist on the card; `title`/
    `description`/`condition` only exist on detail; `country`/`is_kids`
    aren't exposed by ScrapeBadger at all and are always None (None passes
    both filters by design -- only-positive-evidence)."""
    title = (detail.get("title") or "").strip()
    description = (detail.get("description") or "").strip()
    # Observed live: description's first line duplicates the title
    # ("-size 6 black lululemon speedup shorts low rise + ..."), so
    # concatenating both would double up the same text. Only prepend title
    # when description doesn't already start with it.
    if title and description.casefold().startswith(title.casefold()):
        combined_title = description
    else:
        combined_title = f"{title} {description}".strip()

    return {
        "id": card["slug"],
        "title": combined_title,
        "price": float(card["price"]),
        "currency": card["currency"],
        "size": card.get("size"),
        "url": card["url"],
        "image_url": card.get("image"),
        "country": None,
        "condition": _map_condition(detail.get("condition")),
        "is_kids": None,
    }


def _extract_product_objects(html: str) -> list[dict]:
    """Pull the list of raw product dicts out of the page's embedded React
    Server Component payload. Raises DepopResponseSchemaError if the
    expected structure isn't found."""
    chunks = _extract_next_f_chunks(html)
    if not chunks:
        raise DepopResponseSchemaError(
            "No self.__next_f.push(...) RSC chunks found in the search page "
            "HTML — Depop's frontend rendering approach may have changed."
        )

    try:
        full_text = "".join(json.loads('"' + chunk + '"') for chunk in chunks)
    except json.JSONDecodeError as exc:
        raise DepopResponseSchemaError(
            f"Failed to JS-unescape an RSC chunk: {exc}"
        ) from exc

    product_objects: list[dict] = []
    search_from = 0
    while True:
        idx = full_text.find(_OBJECTS_KEY, search_from)
        if idx == -1:
            break
        array_start = idx + len(_OBJECTS_KEY) - 1  # index of the '['
        array_text = _extract_balanced(full_text, array_start)
        search_from = array_start + len(array_text)
        try:
            candidate = json.loads(array_text)
        except json.JSONDecodeError:
            continue
        if candidate and isinstance(candidate[0], dict) and "pricing" in candidate[0]:
            product_objects.extend(candidate)

    if not product_objects and '"total_count":0' not in full_text:
        # No candidate "objects" array with product-shaped entries was found
        # at all (as opposed to a genuine zero-result search) -> the schema
        # likely changed.
        raise DepopResponseSchemaError(
            "Found RSC payload but no product-shaped \"objects\" array in "
            "it — Depop's search response schema may have changed."
        )

    return product_objects


def _extract_next_f_chunks(html: str) -> list[str]:
    """Find every `self.__next_f.push([1,"<escaped>"])` call and return the
    raw (still JS-escaped) string content of each. Scans char-by-char
    tracking backslash-escapes rather than using a regex like `"(.*?)"` for
    the closing quote — a lazy regex would terminate early on an escaped
    quote that happens to be followed by literal `])` characters inside the
    payload (e.g. a listing description containing `6"])`-shaped text),
    silently truncating the chunk."""
    chunks: list[str] = []
    search_from = 0
    while True:
        start = html.find(_NEXT_CHUNK_PREFIX, search_from)
        if start == -1:
            break
        content_start = start + len(_NEXT_CHUNK_PREFIX)
        i = content_start
        escaped = False
        while i < len(html):
            ch = html[i]
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                # Closing quote of the JS string literal, only valid if
                # immediately followed by the call's closing "])".
                if html[i + 1 : i + 3] == "])":
                    break
            i += 1
        else:
            raise DepopResponseSchemaError(
                "Found an unterminated self.__next_f.push(...) chunk while "
                "scanning the search page HTML."
            )
        chunks.append(html[content_start:i])
        search_from = i + 3
    return chunks


def _extract_balanced(text: str, start_idx: int) -> str:
    """Return the substring of `text` starting at `start_idx` (which must be
    an opening '[' or '{') through its matching closing bracket, respecting
    string literals so brackets inside strings (e.g. URLs) aren't counted."""
    open_ch = text[start_idx]
    close_ch = "]" if open_ch == "[" else "}"
    depth = 0
    in_string = False
    escaped = False
    for i in range(start_idx, len(text)):
        ch = text[i]
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
        else:
            if ch == '"':
                in_string = True
            elif ch == open_ch:
                depth += 1
            elif ch == close_ch:
                depth -= 1
                if depth == 0:
                    return text[start_idx : i + 1]
    raise DepopResponseSchemaError(
        "Unbalanced brackets while extracting the products array from the "
        "RSC payload — Depop's response may have been truncated or changed shape."
    )


def _normalize_product(obj: dict) -> dict:
    """Convert one raw Depop product dict into this module's normalized
    shape. Lets KeyError propagate for genuinely required fields — a
    missing required field means Depop's schema changed, which should crash
    loudly rather than produce a half-populated listing."""
    sizes = obj.get("sizes") or []
    size = sizes[0]["name"] if sizes else None

    preview = obj.get("preview") or {}
    image_url = preview.get("formats", {}).get("P0", {}).get("url")
    if image_url is None:
        pictures = obj.get("pictures") or []
        if pictures:
            image_url = pictures[0].get("formats", {}).get("P0", {}).get("url")

    attributes = obj.get("attributes") or {}

    return {
        "id": str(obj["id"]),
        "title": obj.get("description") or "",
        "price": float(obj["pricing"]["current_price"]["total_price"]),
        "currency": obj["pricing"]["currency"],
        "size": size,
        "url": f"https://www.depop.com/products/{obj['slug']}/",
        "image_url": image_url,
        "country": obj.get("country"),
        "condition": attributes.get("condition"),
        "is_kids": attributes.get("is_kids"),
    }


def main() -> None:
    # Windows landmine: listing titles/descriptions can contain emoji, which
    # crash bare stdout prints on the default Windows console codepage.
    sys.stdout.reconfigure(encoding="utf-8")

    listings = fetch_listings(config.SEARCH_QUERY)
    print(f"Query: {config.SEARCH_QUERY!r}")
    print(f"Listings returned: {len(listings)}")
    for listing in listings[:5]:
        print("-" * 60)
        print(f"title: {listing['title']}")
        print(f"price: {listing['price']} {listing['currency']}")
        print(f"size:  {listing['size']}")
        print(f"url:   {listing['url']}")


if __name__ == "__main__":
    main()
