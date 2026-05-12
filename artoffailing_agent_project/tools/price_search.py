"""
price_search.py — blacksun-agent tool

Search the web for product prices using DuckDuckGo.
No API key required. Targets Canadian retailers by default.
Author: ropeadope62 - Dave C
GitHub: https://github.com/ropeadope62/
"""

import re
import logging
import urllib.request
import urllib.parse
from mcp.server import FastMCP

logger = logging.getLogger("workstation-agent.price_search")

# Canadian retailer site filters — used to scope searches
RETAILERS: dict[str, str] = {
    "amazon":           "site:amazon.ca",
    "bestbuy":          "site:bestbuy.ca",
    "canadacomputers":  "site:canadacomputers.com",
    "memoryexpress":    "site:memoryexpress.com",
    "newegg":           "site:newegg.ca",
    "walmart":          "site:walmart.ca",
    "costco":           "site:costco.ca",
    "staples":          "site:staples.ca",
    "thesource":        "site:thesource.ca",
    "bhphotovideo":     "site:bhphotovideo.com",
    "adorama":          "site:adorama.com",
}

# Regex to detect price patterns like $12.99 or $1,299
_PRICE_RE = re.compile(r"\$\s*[\d,]+(?:\.\d{1,2})?")


def _fetch(url: str, timeout: int = 10) -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0 Safari/537.36"
            ),
            "Accept-Language": "en-CA,en;q=0.9",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _strip_tags(html: str) -> str:
    return re.sub(r"<[^>]+>", "", html).strip()


def _decode_ddg_url(redirect_href: str) -> str:
    """Extract the real URL from a DuckDuckGo redirect href like //duckduckgo.com/l/?uddg=..."""
    if redirect_href.startswith("//"):
        redirect_href = "https:" + redirect_href
    parsed = urllib.parse.urlparse(redirect_href)
    params = urllib.parse.parse_qs(parsed.query)
    uddg = params.get("uddg", [None])[0]
    if uddg:
        return urllib.parse.unquote(uddg)
    return redirect_href


def _search_ddg(query: str, max_results: int = 10) -> list[dict]:
    """Search DuckDuckGo Lite and return parsed results."""
    url = f"https://lite.duckduckgo.com/lite/?q={urllib.parse.quote_plus(query)}"
    try:
        html = _fetch(url)
    except Exception as e:
        logger.warning(f"DuckDuckGo search failed for '{query}': {e}")
        return []

    # DDG Lite uses single-quoted class attributes and redirect hrefs.
    # Title: <a rel="nofollow" href="//duckduckgo.com/l/?uddg=<encoded>&rut=..." class='result-link'>Title</a>
    # Snippet: <td class='result-snippet'>...</td>
    # Display URL: <span class='link-text'>www.example.com/...</span>

    # Extract href + title — href uses double quotes, class uses single quotes
    title_links = re.findall(
        r'href="(//duckduckgo\.com/l/\?[^"]+)"[^>]*class=\'result-link\'[^>]*>(.*?)</a>',
        html, re.DOTALL
    )
    snippets = re.findall(
        r"<td[^>]*class='result-snippet'[^>]*>(.*?)</td>",
        html, re.DOTALL
    )
    display_urls = re.findall(
        r"<span[^>]*class='link-text'[^>]*>(.*?)</span>",
        html, re.DOTALL
    )

    results = []
    for i, (redirect_href, title_html) in enumerate(title_links[:max_results]):
        title = _strip_tags(title_html)
        snippet = _strip_tags(snippets[i]) if i < len(snippets) else ""
        display = _strip_tags(display_urls[i]) if i < len(display_urls) else ""
        real_url = _decode_ddg_url(redirect_href)

        # Skip DDG ad/redirect URLs
        if "duckduckgo.com/y.js" in real_url or real_url.startswith("https://duckduckgo.com/y.js"):
            continue

        combined = f"{title} {snippet}"
        prices = _PRICE_RE.findall(combined)

        results.append({
            "title": title,
            "url": real_url,
            "display_url": display,
            "snippet": snippet[:200],
            "prices_found": prices,
        })

    return results


def _format_results(query: str, results: list[dict]) -> str:
    if not results:
        return f"No results found for: {query}"

    lines = [f"## Results for: {query}\n"]

    for r in results:
        price_str = "  \n  💰 " + " / ".join(r["prices_found"]) if r["prices_found"] else ""
        lines.append(f"### [{r['title']}]({r['url']})")
        lines.append(f"*{r['display_url']}*")
        if r["snippet"]:
            lines.append(r["snippet"])
        if price_str:
            lines.append(price_str)
        lines.append("")

    return "\n".join(lines)


def register_price_search(mcp: FastMCP):

    @mcp.tool()
    def search_prices(
        product: str,
        retailers: str = "",
        max_results: int = 8,
    ) -> str:
        """
        Search the web for the best prices on a product.

        Uses DuckDuckGo to find current listings and pricing. Optionally
        scopes the search to specific Canadian retailers.

        Args:
            product:     What you want to find pricing for, e.g. 'RTX 5080 GPU'
                         or 'Sony WH-1000XM5 headphones'.
            retailers:   Comma-separated list of retailers to scope the search.
                         Supported: amazon, bestbuy, canadacomputers, memoryexpress,
                         newegg, walmart, costco, staples, thesource, bhphotovideo, adorama.
                         Leave empty to search across all sites.
            max_results: Maximum number of results to return per query (default 8).
        """
        retailer_list = [r.strip().lower() for r in retailers.split(",") if r.strip()]

        if retailer_list:
            # One search per retailer, collect and merge
            all_results: list[dict] = []
            seen_urls: set[str] = set()

            for retailer in retailer_list:
                if retailer not in RETAILERS:
                    continue
                site_filter = RETAILERS[retailer]
                q = f'buy "{product}" {site_filter} price'
                items = _search_ddg(q, max_results=max_results)
                for item in items:
                    if item["url"] not in seen_urls:
                        seen_urls.add(item["url"])
                        all_results.append(item)

            if not all_results:
                # Fall back to broad search
                all_results = _search_ddg(f'buy "{product}" canada best price', max_results)

            # Sort: results with prices first
            all_results.sort(key=lambda x: (not bool(x["prices_found"]),))
            return _format_results(product, all_results[:max_results * len(retailer_list)])

        else:
            # General best-price search
            query = f'buy "{product}" best price canada'
            results = _search_ddg(query, max_results)
            results.sort(key=lambda x: (not bool(x["prices_found"]),))
            return _format_results(product, results)

    @mcp.tool()
    def compare_prices(
        product: str,
        max_results: int = 5,
    ) -> str:
        """
        Compare prices for a product across the major Canadian retailers.

        Searches Amazon.ca, Best Buy, Canada Computers, Memory Express, and
        Newegg simultaneously and returns a combined, deduplicated price report.

        Args:
            product:     The product to compare prices for.
            max_results: Max results per retailer (default 5).
        """
        target_retailers = ["amazon", "bestbuy", "canadacomputers", "memoryexpress", "newegg"]
        sections: list[str] = [f"# Price Comparison: {product}\n"]

        for retailer in target_retailers:
            site_filter = RETAILERS[retailer]
            q = f'"{product}" {site_filter}'
            results = _search_ddg(q, max_results=max_results)

            heading = retailer.replace("canadacomputers", "Canada Computers").replace(
                "memoryexpress", "Memory Express"
            ).replace("bestbuy", "Best Buy").replace("newegg", "Newegg").replace(
                "amazon", "Amazon.ca"
            )
            sections.append(f"## {heading}\n")

            if not results:
                sections.append("_No results found._\n")
                continue

            for r in results:
                price_str = " — 💰 " + " / ".join(r["prices_found"]) if r["prices_found"] else ""
                sections.append(f"- [{r['title']}]({r['url']}){price_str}")
                if r["snippet"] and not r["prices_found"]:
                    sections.append(f"  _{r['snippet'][:120]}_")
            sections.append("")

        return "\n".join(sections)

    @mcp.tool()
    def list_price_search_retailers() -> str:
        """List the supported retailers for price searching."""
        lines = ["**Supported retailers for price_search:**\n"]
        for name in sorted(RETAILERS):
            lines.append(f"- `{name}`")
        return "\n".join(lines)
