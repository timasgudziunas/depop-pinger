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

import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# --- Tunables -----------------------------------------------------------

SEARCH_URL = "https://www.depop.com/search/"
REQUEST_TIMEOUT_SECONDS = 15
# Best-effort "most recent first" sort value (see module docstring gotchas).
SORT_VALUE = "newest"
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


def fetch_listings(query: str) -> list[dict]:
    """Fetch current live Depop listings matching `query`.

    Returns a list of normalized dicts with keys: id (str), title (str),
    price (float), currency (str), size (str or None), url (str),
    image_url (str or None). Sorted best-effort newest-first (see module
    docstring). Returns an empty list on transient network errors (logged)
    or on a genuine zero-result search. Raises DepopResponseSchemaError if
    Depop's response no longer matches the expected shape.
    """
    html = _fetch_search_html(query)
    if html is None:
        return []

    product_objects = _extract_product_objects(html)
    # The RSC payload can contain more than one product-shaped "objects"
    # array; dedupe by id (order-preserving) so one run never yields the
    # same listing twice.
    unique_by_id: dict[str, dict] = {}
    for obj in product_objects:
        unique_by_id.setdefault(str(obj["id"]), obj)
    listings = [_normalize_product(obj) for obj in unique_by_id.values()]
    logger.info("fetch_listings(%r): %d listings returned", query, len(listings))
    return listings


def _fetch_search_html(query: str) -> str | None:
    """GET the Depop search results page. Returns the HTML body, or None on
    a transient network error / non-recoverable HTTP status (logged)."""
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

    return {
        "id": str(obj["id"]),
        "title": obj.get("description") or "",
        "price": float(obj["pricing"]["current_price"]["total_price"]),
        "currency": obj["pricing"]["currency"],
        "size": size,
        "url": f"https://www.depop.com/products/{obj['slug']}/",
        "image_url": image_url,
    }


def main() -> None:
    # Windows landmine: listing titles/descriptions can contain emoji, which
    # crash bare stdout prints on the default Windows console codepage.
    sys.stdout.reconfigure(encoding="utf-8")

    import config

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
