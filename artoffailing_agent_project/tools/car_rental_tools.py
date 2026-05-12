"""
car_rental_tools.py - MCP tools for car rental search and comparison

Provides lightweight web search, page fetch, extraction, normalization,
and ranking helpers for public car rental pages.
Author: ropeadope62 - Dave C
GitHub: https://github.com/ropeadope62/
"""

import json
import logging
import re
import urllib.parse
import urllib.request
from html import unescape
from urllib.parse import urlparse

from mcp.server.fastmcp import FastMCP

logger = logging.getLogger("workstation-agent.car-rental")

_PRICE_RE = re.compile(r"(?P<currency>CAD|USD|EUR|GBP|C\$|US\$|\$|€|£)\s?(?P<amount>[\d,]+(?:\.\d{1,2})?)", re.IGNORECASE)
_JSON_LD_RE = re.compile(
    r'<script[^>]+type="application/ld\+json"[^>]*>(.*?)</script>',
    re.IGNORECASE | re.DOTALL,
)
_STRIP_TAGS_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")

_DIRECT_BOOKING_DOMAINS = {
    "enterprise.com",
    "nationalcar.com",
    "alamo.com",
    "hertz.com",
    "avis.com",
    "budget.com",
    "sixt.com",
    "thrifty.com",
    "dollar.com",
    "europcar.com",
}

_THIRD_PARTY_DOMAINS = {
    "kayak.com",
    "expedia.com",
    "priceline.com",
    "booking.com",
    "carrentals.com",
    "discovercars.com",
    "rentalcars.com",
    "travelocity.com",
}


def _fetch(url: str, timeout: int = 15) -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0 Safari/537.36"
            ),
            "Accept-Language": "en-CA,en;q=0.9,en-US;q=0.8",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _strip_tags(html: str) -> str:
    return _WHITESPACE_RE.sub(" ", unescape(_STRIP_TAGS_RE.sub(" ", html))).strip()


def _decode_ddg_url(redirect_href: str) -> str:
    if redirect_href.startswith("//"):
        redirect_href = "https:" + redirect_href
    parsed = urllib.parse.urlparse(redirect_href)
    params = urllib.parse.parse_qs(parsed.query)
    uddg = params.get("uddg", [None])[0]
    if uddg:
        return urllib.parse.unquote(uddg)
    return redirect_href


def _search_ddg(query: str, max_results: int = 10) -> list[dict]:
    url = f"https://lite.duckduckgo.com/lite/?q={urllib.parse.quote_plus(query)}"
    try:
        html = _fetch(url)
    except Exception as exc:
        logger.warning("DuckDuckGo search failed for '%s': %s", query, exc)
        return []

    title_links = re.findall(
        r'href="(//duckduckgo\.com/l/\?[^\"]+)"[^>]*class=\'result-link\'[^>]*>(.*?)</a>',
        html,
        re.DOTALL,
    )
    snippets = re.findall(r"<td[^>]*class='result-snippet'[^>]*>(.*?)</td>", html, re.DOTALL)
    display_urls = re.findall(r"<span[^>]*class='link-text'[^>]*>(.*?)</span>", html, re.DOTALL)

    results = []
    for index, (redirect_href, title_html) in enumerate(title_links[:max_results]):
        title = _strip_tags(title_html)
        snippet = _strip_tags(snippets[index]) if index < len(snippets) else ""
        display = _strip_tags(display_urls[index]) if index < len(display_urls) else ""
        real_url = _decode_ddg_url(redirect_href)
        if "duckduckgo.com/y.js" in real_url:
            continue
        results.append(
            {
                "title": title,
                "url": real_url,
                "display_url": display,
                "snippet": snippet[:300],
                "prices_found": [m.group(0) for m in _PRICE_RE.finditer(f"{title} {snippet}")],
            }
        )
    return results


def _parse_price(value: str) -> dict | None:
    if not value:
        return None
    match = _PRICE_RE.search(value)
    if not match:
        return None
    currency = match.group("currency").upper().replace("C$", "CAD").replace("US$", "USD")
    if currency == "$":
        currency = "USD/CAD_UNSPECIFIED"
    amount = float(match.group("amount").replace(",", ""))
    return {"amount": amount, "currency": currency, "display": match.group(0)}


def _extract_text_window(text: str, pattern: str, radius: int = 180) -> str:
    match = re.search(pattern, text, re.IGNORECASE)
    if not match:
        return ""
    start = max(0, match.start() - radius)
    end = min(len(text), match.end() + radius)
    return text[start:end].strip()


def _detect_policy(text: str, keywords: list[str], fallback: str = "") -> str:
    for keyword in keywords:
        window = _extract_text_window(text, keyword)
        if window:
            return window
    return fallback


def _domain_kind(source_url: str) -> str:
    host = urlparse(source_url).netloc.lower().replace("www.", "")
    if any(host.endswith(domain) for domain in _DIRECT_BOOKING_DOMAINS):
        return "direct"
    if any(host.endswith(domain) for domain in _THIRD_PARTY_DOMAINS):
        return "third_party"
    return "unknown"


def _extract_json_ld_options(html: str, source_url: str) -> list[dict]:
    options: list[dict] = []
    for block in _JSON_LD_RE.findall(html):
        try:
            payload = json.loads(unescape(block.strip()))
        except Exception:
            continue

        candidates = payload if isinstance(payload, list) else [payload]
        for item in candidates:
            if not isinstance(item, dict):
                continue
            offers = item.get("offers")
            if not offers:
                continue
            offer_list = offers if isinstance(offers, list) else [offers]
            for offer in offer_list:
                if not isinstance(offer, dict):
                    continue
                amount = offer.get("price")
                currency = offer.get("priceCurrency")
                display = f"{currency} {amount}" if currency and amount else ""
                options.append(
                    {
                        "vehicle": item.get("name") or item.get("model") or item.get("@type") or "Unknown vehicle",
                        "source_url": source_url,
                        "provider": urlparse(source_url).netloc,
                        "booking_source_type": _domain_kind(source_url),
                        "availability_confirmed": str(offer.get("availability", "")).lower().endswith("instock"),
                        "estimated_total": {"amount": float(amount), "currency": currency, "display": display} if amount else None,
                        "base_price": {"amount": float(amount), "currency": currency, "display": display} if amount else None,
                        "taxes_and_fees": None,
                        "cancellation_policy": "",
                        "mileage_policy": "",
                        "insurance_notes": "",
                        "deposit_policy": "",
                        "pickup_dropoff_notes": "",
                        "risks": [],
                    }
                )
    return options


def _extract_heuristic_options(html: str, source_url: str) -> list[dict]:
    text = _strip_tags(html)
    lines = [line.strip() for line in re.split(r"[\r\n]+", text) if line.strip()]
    host = urlparse(source_url).netloc.lower().replace("www.", "")
    prices = [_parse_price(match.group(0)) for match in _PRICE_RE.finditer(text)]
    prices = [price for price in prices if price]
    titles = [line for line in lines if len(line) < 120 and re.search(r"car|suv|truck|van|rental|compact|intermediate|economy|premium|luxury", line, re.IGNORECASE)]

    vehicle = titles[0] if titles else host
    estimated_total = prices[0] if prices else None
    base_price = prices[1] if len(prices) > 1 else estimated_total
    taxes = prices[2] if len(prices) > 2 else None

    availability_confirmed = bool(re.search(r"book now|reserve now|available|select vehicle|choose car", text, re.IGNORECASE))
    cancellation_policy = _detect_policy(text, [r"free cancellation", r"non-refundable", r"cancel", r"modification policy"])
    mileage_policy = _detect_policy(text, [r"unlimited mileage", r"limited mileage", r"km included", r"miles included"])
    insurance_notes = _detect_policy(text, [r"insurance", r"collision damage waiver", r"liability", r"coverage"])
    deposit_policy = _detect_policy(text, [r"deposit", r"credit card hold", r"authorization hold", r"security hold"])
    pickup_notes = _detect_policy(text, [r"airport", r"terminal", r"shuttle", r"pickup", r"drop-off", r"dropoff"])

    risks = []
    if _domain_kind(source_url) == "third_party":
        risks.append("Third-party booking source. Support and change handling may be weaker than direct booking.")
    if not cancellation_policy:
        risks.append("Cancellation policy not clearly surfaced on the captured page.")
    if not mileage_policy:
        risks.append("Mileage policy not clearly surfaced on the captured page.")
    if deposit_policy and re.search(r"\$|CAD|USD|€|£", deposit_policy):
        risks.append("Credit card hold or deposit appears to apply.")

    return [
        {
            "vehicle": vehicle,
            "source_url": source_url,
            "provider": host,
            "booking_source_type": _domain_kind(source_url),
            "availability_confirmed": availability_confirmed,
            "estimated_total": estimated_total,
            "base_price": base_price,
            "taxes_and_fees": taxes,
            "cancellation_policy": cancellation_policy,
            "mileage_policy": mileage_policy,
            "insurance_notes": insurance_notes,
            "deposit_policy": deposit_policy,
            "pickup_dropoff_notes": pickup_notes,
            "risks": risks,
        }
    ]


def _safe_json_loads(payload: str, default):
    try:
        return json.loads(payload)
    except Exception:
        return default


def register_car_rental_tools(mcp: FastMCP):

    @mcp.tool()
    def web_search(query: str, location: str = "", date_range: str = "", max_results: int = 8) -> str:
        """Search the web for car rental options, company pages, aggregators, and policy pages.

        Args:
            query: Search query or trip summary.
            location: Optional pickup city or airport.
            date_range: Optional date/time range text.
            max_results: Maximum results to return.
        """
        parts = [query, location, date_range, "car rental"]
        search_query = " ".join(part for part in parts if part).strip()
        results = _search_ddg(search_query, max_results=max_results)
        return json.dumps(results, indent=2)

    @mcp.tool()
    def fetch_page(url: str) -> str:
        """Retrieve a public webpage for extraction.

        Args:
            url: Public URL to fetch.
        """
        try:
            return _fetch(url)
        except Exception as exc:
            return json.dumps({"error": str(exc), "url": url})

    @mcp.tool()
    def extract_rental_options(html: str, source_url: str) -> str:
        """Extract structured rental listing data from a webpage.

        Args:
            html: Raw page HTML.
            source_url: Source page URL.
        """
        if not html or html.lstrip().startswith("{"):
            return json.dumps([], indent=2)

        options = _extract_json_ld_options(html, source_url)
        if not options:
            options = _extract_heuristic_options(html, source_url)
        return json.dumps(options, indent=2)

    @mcp.tool()
    def normalize_prices(rental_options: str) -> str:
        """Normalize prices, taxes, fees, and currency into comparable totals.

        Args:
            rental_options: JSON array of extracted rental options.
        """
        options = _safe_json_loads(rental_options, [])
        normalized = []

        for option in options:
            if not isinstance(option, dict):
                continue
            base_price = option.get("base_price") or {}
            total = option.get("estimated_total") or {}
            taxes = option.get("taxes_and_fees") or {}

            base_amount = float(base_price.get("amount") or 0)
            total_amount = float(total.get("amount") or 0)
            taxes_amount = float(taxes.get("amount") or 0)

            if total_amount <= 0 and base_amount > 0:
                total_amount = base_amount + taxes_amount

            currency = total.get("currency") or base_price.get("currency") or taxes.get("currency") or "UNKNOWN"
            fee_visibility = "clear" if taxes_amount > 0 or option.get("taxes_and_fees") else "unclear"

            normalized.append(
                {
                    **option,
                    "normalized_total": {
                        "amount": round(total_amount, 2),
                        "currency": currency,
                        "display": f"{currency} {round(total_amount, 2):.2f}" if total_amount > 0 else "",
                    },
                    "fee_visibility": fee_visibility,
                }
            )

        return json.dumps(normalized, indent=2)

    @mcp.tool()
    def rank_rental_options(rental_options: str, user_preferences: str = "{}") -> str:
        """Rank rental options based on price, flexibility, transparency, and user fit.

        Args:
            rental_options: JSON array of rental options.
            user_preferences: JSON object of user preferences.
        """
        options = _safe_json_loads(rental_options, [])
        preferences = _safe_json_loads(user_preferences, {})
        budget = float(preferences.get("budget") or 0)
        preferred_vehicle = str(preferences.get("vehicle_type") or "").lower().strip()
        airport_preference = str(preferences.get("pickup_preference") or "").lower().strip()

        ranked = []
        for option in options:
            if not isinstance(option, dict):
                continue
            score = 0
            reasons = []
            risks = list(option.get("risks") or [])

            normalized_total = option.get("normalized_total") or option.get("estimated_total") or {}
            total_amount = float(normalized_total.get("amount") or 0)
            vehicle_name = str(option.get("vehicle") or "").lower()
            pickup_notes = str(option.get("pickup_dropoff_notes") or "").lower()
            cancellation_policy = str(option.get("cancellation_policy") or "").lower()
            mileage_policy = str(option.get("mileage_policy") or "").lower()
            source_type = option.get("booking_source_type") or "unknown"
            availability_confirmed = bool(option.get("availability_confirmed"))
            fee_visibility = option.get("fee_visibility") or "unclear"

            if availability_confirmed:
                score += 30
                reasons.append("Availability appears confirmed on source page.")
            else:
                risks.append("Availability not clearly confirmed on source page.")

            if total_amount > 0:
                score += 20
                reasons.append("Usable total price was extracted.")
            else:
                risks.append("Total price is incomplete or unclear.")

            if fee_visibility == "clear":
                score += 10
                reasons.append("Taxes or mandatory fees are partially surfaced.")
            else:
                risks.append("Taxes and fees may be incomplete.")

            if "free cancellation" in cancellation_policy:
                score += 10
                reasons.append("Free cancellation is mentioned.")
            elif "non-refundable" in cancellation_policy:
                score -= 8
                risks.append("Rate appears non-refundable.")

            if "unlimited" in mileage_policy:
                score += 8
                reasons.append("Unlimited mileage is mentioned.")
            elif mileage_policy:
                score -= 3
                risks.append("Mileage appears restricted or unclear.")

            if source_type == "direct":
                score += 12
                reasons.append("Direct booking source.")
            elif source_type == "third_party":
                score -= 10

            if budget > 0 and total_amount > 0:
                if total_amount <= budget:
                    score += 6
                    reasons.append("Within stated budget.")
                else:
                    score -= 6
                    risks.append("Above stated budget.")

            if preferred_vehicle and preferred_vehicle in vehicle_name:
                score += 6
                reasons.append("Vehicle type aligns with stated preference.")

            if airport_preference:
                if airport_preference == "airport" and "airport" in pickup_notes:
                    score += 4
                elif airport_preference == "city" and "airport" in pickup_notes:
                    score -= 2

            ranked.append(
                {
                    **option,
                    "score": score,
                    "reasons": reasons,
                    "risks": list(dict.fromkeys(risks)),
                }
            )

        ranked.sort(
            key=lambda item: (
                -int(item.get("score") or 0),
                float((item.get("normalized_total") or {}).get("amount") or 999999),
            )
        )
        return json.dumps(ranked, indent=2)