from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from functools import lru_cache
from html import unescape
from html.parser import HTMLParser
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, quote_plus, unquote, urlparse
from urllib.request import Request, urlopen
from uuid import uuid4


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


HTTP_TIMEOUT_SECONDS = float(os.getenv("BLOCKYBY_HTTP_TIMEOUT_SECONDS", "2"))
MAX_WEB_RESULTS_PER_ITEM = int(os.getenv("BLOCKYBY_MAX_WEB_RESULTS_PER_ITEM", "2"))
BLOCKYBY_USER_AGENT = "BlockybyProductSourcingAgent/0.3"

SUPPLIER_HINTS = [
    "digikey",
    "mouser",
    "rs-online",
    "farnell",
    "element14",
    "adafruit",
    "sparkfun",
    "thepihut",
    "pimoroni",
    "arduino.cc",
    "prusa3d",
    "3djake",
    "amazon",
    "screwfix",
    "toolstation",
    "diy.com",
    "pololu",
    "reichelt",
]

BLOCKED_RESULT_HOSTS = {
    "google.com",
    "duckduckgo.com",
    "bing.com",
    "youtube.com",
    "wikipedia.org",
    "reddit.com",
    "pinterest.com",
}


class SearchResultParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.results = []
        self._current = None
        self._field = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = dict(attrs)
        classes = set((attr.get("class") or "").split())
        if tag == "a" and "result__a" in classes:
            self._current = {"title": "", "url": self._clean_duckduckgo_url(attr.get("href") or ""), "snippet": ""}
            self._field = "title"
        elif self._current is not None and tag in {"a", "div"} and ("result__snippet" in classes or "result__body" in classes):
            self._field = "snippet"

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._field == "title":
            self._field = None
        if tag == "div" and self._current and self._current.get("title") and self._current.get("url"):
            self.results.append(self._current)
            self._current = None
            self._field = None

    def handle_data(self, data: str) -> None:
        if self._current is not None and self._field:
            self._current[self._field] = (self._current.get(self._field, "") + " " + data).strip()

    @staticmethod
    def _clean_duckduckgo_url(url: str) -> str:
        parsed = urlparse(url)
        if "duckduckgo.com" in parsed.netloc and parsed.path.startswith("/l/"):
            target = parse_qs(parsed.query).get("uddg", [""])[0]
            if target:
                return unquote(target)
        return url


def compact_text(value: Any) -> str:
    return re.sub(r"\s+", " ", unescape(str(value or ""))).strip()


def is_http_url(url: str) -> bool:
    parsed = urlparse(str(url or ""))
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def host_is_useful_product_source(url: str) -> bool:
    host = urlparse(url).netloc.lower().removeprefix("www.")
    if not host or any(host == blocked or host.endswith("." + blocked) for blocked in BLOCKED_RESULT_HOSTS):
        return False
    return any(hint in host for hint in SUPPLIER_HINTS)


def supplier_name_from_url(url: str) -> str:
    host = urlparse(url).netloc.lower().removeprefix("www.")
    if not host:
        return "Unknown supplier"
    parts = [part for part in host.split(".") if part not in {"ie", "uk", "com", "co", "store"}]
    name = (parts[0] if parts else host.split(".")[0]).replace("-", " ").replace("_", " ")
    return name.title()


def safe_request(url: str, method: str = "GET") -> Request:
    return Request(url, method=method, headers={"User-Agent": BLOCKYBY_USER_AGENT, "Accept": "text/html,application/xhtml+xml"})


def probe_url(url: str) -> dict[str, Any]:
    if not is_http_url(url):
        return {"url": url, "ok": False, "statusCode": None, "message": "Missing or non-HTTP(S) URL."}

    if os.getenv("BLOCKYBY_LIVE_LINK_CHECKS", "1").lower() in {"0", "false", "no"}:
        return {"url": url, "ok": False, "statusCode": None, "message": "Live link checks are disabled."}

    for method in ["HEAD", "GET"]:
        try:
            with urlopen(safe_request(url, method), timeout=HTTP_TIMEOUT_SECONDS) as response:
                status = int(getattr(response, "status", 200))
                return {"url": response.geturl(), "ok": 200 <= status < 400, "statusCode": status, "method": method, "message": f"{method} returned HTTP {status}."}
        except HTTPError as exc:
            if method == "HEAD" and exc.code in {403, 405, 429, 503}:
                continue
            return {"url": url, "ok": 200 <= int(exc.code) < 400, "statusCode": int(exc.code), "method": method, "message": f"{method} returned HTTP {exc.code}."}
        except (TimeoutError, URLError, OSError) as exc:
            if method == "HEAD":
                continue
            return {"url": url, "ok": False, "statusCode": None, "method": method, "message": f"Could not verify URL: {exc}"}
    return {"url": url, "ok": False, "statusCode": None, "message": "Could not verify URL."}


@lru_cache(maxsize=256)
def cached_search_results(query: str, limit: int) -> tuple[tuple[str, str, str], ...]:
    if os.getenv("BLOCKYBY_WEB_SEARCH", "1").lower() in {"0", "false", "no"}:
        return ()
    results = fetch_bing_search_results(query, limit)
    if results:
        return tuple((result["title"], result["url"], result["snippet"]) for result in results)
    results = fetch_duckduckgo_search_results(query, limit)
    return tuple((result["title"], result["url"], result["snippet"]) for result in results)


def fetch_search_results(query: str, limit: int = MAX_WEB_RESULTS_PER_ITEM) -> list[dict[str, str]]:
    return [
        {"title": title, "url": url, "snippet": snippet}
        for title, url, snippet in cached_search_results(query, limit)
    ]


def extract_html_text(html: str) -> str:
    text = re.sub(r"<script\b.*?</script>", " ", html, flags=re.I | re.S)
    text = re.sub(r"<style\b.*?</style>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    return compact_text(text)


def clean_bing_url(url: str) -> str:
    parsed = urlparse(unescape(url))
    if "bing.com" in parsed.netloc and parsed.path.startswith("/ck/a"):
        target = parse_qs(parsed.query).get("u", [""])[0]
        if target.startswith("a1"):
            try:
                import base64
                padded = target[2:] + "=" * (-len(target[2:]) % 4)
                return base64.urlsafe_b64decode(padded.encode()).decode("utf-8", errors="ignore")
            except Exception:
                return url
    return unescape(url)


def fetch_bing_search_results(query: str, limit: int) -> list[dict[str, str]]:
    url = f"https://www.bing.com/search?q={quote_plus(query)}"
    try:
        with urlopen(safe_request(url), timeout=HTTP_TIMEOUT_SECONDS) as response:
            html = response.read(900_000).decode("utf-8", errors="replace")
    except (TimeoutError, URLError, OSError):
        return []

    results = []
    chunks = re.split(r"<li\b[^>]*class=\"[^\"]*\bb_algo\b[^\"]*\"[^>]*>", html, flags=re.I)
    for chunk in chunks[1:]:
        chunk = chunk.split("</li>", 1)[0]
        link = re.search(r"<h2[^>]*>.*?<a\b[^>]*href=\"([^\"]+)\"[^>]*>(.*?)</a>", chunk, flags=re.I | re.S)
        if not link:
            continue
        product_url = clean_bing_url(link.group(1))
        if not is_http_url(product_url) or not host_is_useful_product_source(product_url):
            continue
        snippet_match = re.search(r"<p[^>]*>(.*?)</p>", chunk, flags=re.I | re.S)
        results.append({
            "title": extract_html_text(link.group(2)),
            "url": product_url,
            "snippet": extract_html_text(snippet_match.group(1) if snippet_match else ""),
        })
        if len(results) >= limit:
            break
    return results


def fetch_duckduckgo_search_results(query: str, limit: int) -> list[dict[str, str]]:
    url = f"https://duckduckgo.com/html/?q={quote_plus(query)}"
    try:
        with urlopen(safe_request(url), timeout=HTTP_TIMEOUT_SECONDS) as response:
            html = response.read(750_000).decode("utf-8", errors="replace")
    except (TimeoutError, URLError, OSError):
        return []

    parser = SearchResultParser()
    parser.feed(html)
    deduped = []
    seen = set()
    for result in parser.results:
        product_url = result.get("url", "")
        if not is_http_url(product_url) or not host_is_useful_product_source(product_url):
            continue
        normalized = product_url.rstrip("/")
        if normalized in seen:
            continue
        seen.add(normalized)
        deduped.append({
            "title": compact_text(result.get("title")),
            "url": product_url,
            "snippet": compact_text(result.get("snippet")),
        })
        if len(deduped) >= limit:
            break
    return deduped


def make_search_queries(item: dict[str, Any]) -> list[str]:
    name = compact_text(item.get("name", ""))
    category = compact_text(item.get("category", ""))
    compatibility = compact_text(item.get("compatibilityNotes", ""))
    base = f"{name} {category}".strip()
    text = f"{base} {compatibility}".lower()
    if any(word in text for word in ["filament", "pla", "petg", "3d print"]):
        sites = ["prusa3d.com", "3djake.ie", "amazon.co.uk"]
    elif any(word in text for word in ["screw", "standoff", "spacer", "wood", "plywood"]):
        sites = ["screwfix.ie", "toolstation.ie", "diy.com", "amazon.co.uk"]
    elif any(word in text for word in ["calipers", "measure"]):
        sites = ["screwfix.ie", "toolstation.ie", "amazon.co.uk"]
    else:
        sites = ["digikey.ie", "mouser.ie", "adafruit.com", "thepihut.com"]
    queries = [f"site:{site} {base} buy price stock" for site in sites]
    queries.append(f"{base} {compatibility[:80]} buy product price stock")
    return queries


def build_web_candidate(item: dict[str, Any], result: dict[str, str], rank: int) -> dict[str, Any]:
    title = result.get("title") or item.get("name") or "Product result"
    snippet = result.get("snippet") or ""
    product_url = result["url"]
    return {
        "supplier": supplier_name_from_url(product_url),
        "productName": title[:160],
        "manufacturer": "",
        "manufacturerPartNumber": "",
        "supplierPartNumber": "",
        "description": snippet[:360] or f"Web result for {item.get('name', 'requested item')}.",
        "productUrl": product_url,
        "datasheetUrl": "",
        "imageUrl": "",
        "unitPrice": 0,
        "currency": "EUR",
        "priceText": "Price not verified. Search snippets are not trusted as product prices.",
        "priceConfidence": "unknown",
        "shippingEstimate": 0,
        "shippingText": "Shipping is unknown until the supplier checkout or delivery page provides it.",
        "shippingConfidence": "unknown",
        "totalPriceEstimate": 0,
        "stockAvailable": None,
        "minimumOrderQuantity": 1,
        "leadTime": "Check product page",
        "sourceType": "web_search",
        "matchScore": max(1, MAX_WEB_RESULTS_PER_ITEM + 1 - rank),
        "evidenceNotes": "Found by live web search, then passed through link verification. Price is intentionally not inferred from snippets.",
    }


def supplier_search_urls_for_item(item: dict[str, Any]) -> list[tuple[str, str]]:
    name = compact_text(item.get("name", ""))
    category = compact_text(item.get("category", ""))
    query = quote_plus(f"{name} {category}".strip())
    text = f"{name} {category} {item.get('compatibilityNotes', '')}".lower()
    if any(word in text for word in ["filament", "pla", "petg", "3d print"]):
        return [
            ("Prusa", f"https://www.prusa3d.com/search/?q={query}"),
            ("3DJake", f"https://www.3djake.ie/search?keyword={query}"),
            ("Amazon UK", f"https://www.amazon.co.uk/s?k={query}"),
        ]
    if any(word in text for word in ["screw", "standoff", "spacer", "wood", "plywood"]):
        return [
            ("Amazon UK", f"https://www.amazon.co.uk/s?k={query}"),
            ("Mouser", f"https://www.mouser.ie/c/?q={query}"),
            ("B&Q", f"https://www.diy.com/search?term={query}"),
        ]
    if any(word in text for word in ["calipers", "measure"]):
        return [
            ("Screwfix", f"https://www.screwfix.ie/search?search={query}"),
            ("Toolstation", f"https://www.toolstation.ie/search?q={query}"),
            ("Amazon UK", f"https://www.amazon.co.uk/s?k={query}"),
        ]
    return [
        ("Digi-Key", f"https://www.digikey.ie/en/products/result?keywords={query}"),
        ("Mouser", f"https://www.mouser.ie/c/?q={query}"),
        ("Adafruit", f"https://www.adafruit.com/search?q={query}"),
        ("The Pi Hut", f"https://thepihut.com/search?q={query}"),
    ]


def supplier_search_source_candidates(item: dict[str, Any]) -> list[dict[str, Any]]:
    candidates = []
    for rank, (supplier, url) in enumerate(supplier_search_urls_for_item(item), start=1):
        candidate = verify_source_candidate({
            "supplier": supplier,
            "productName": f"{supplier} search for {item.get('name', 'part')}",
            "manufacturer": "",
            "manufacturerPartNumber": "",
            "supplierPartNumber": "",
            "description": "Verified supplier search page. Open it to choose a concrete product and confirm final price, stock, and shipping.",
            "productUrl": url,
            "datasheetUrl": "",
            "imageUrl": "",
            "unitPrice": 0,
            "currency": "EUR",
            "priceText": "Unknown until the supplier page is opened and a specific product is selected.",
            "priceConfidence": "unknown",
            "shippingEstimate": 0,
            "shippingText": "Unknown until checkout or the supplier's delivery page gives a live quote.",
            "shippingConfidence": "unknown",
            "totalPriceEstimate": 0,
            "stockAvailable": None,
            "minimumOrderQuantity": 1,
            "leadTime": "Check supplier page",
            "sourceType": "supplier_search",
            "matchScore": max(1, 5 - rank),
            "evidenceNotes": "Generated from trusted supplier search URL template, then verified by HTTP. Link is real; price is not inferred.",
        })
        if candidate.get("verificationStatus") == "verified":
            candidates.append(candidate)
        if len(candidates) >= 2:
            break
    return candidates


def verify_source_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    checked = dict(candidate)
    product_result = probe_url(str(checked.get("productUrl", "")))
    datasheet_url = str(checked.get("datasheetUrl", ""))
    datasheet_result = probe_url(datasheet_url) if datasheet_url else {"url": "", "ok": False, "statusCode": None, "message": "No datasheet URL supplied."}
    product_ok = bool(product_result.get("ok"))

    checked["productUrl"] = product_result.get("url") or checked.get("productUrl", "")
    checked["productUrlVerified"] = product_ok
    checked["datasheetUrlVerified"] = bool(datasheet_url) and bool(datasheet_result.get("ok"))
    checked["verificationStatus"] = "verified" if product_ok else "unverified"
    checked["verificationMethod"] = "live_http_probe"
    checked["verificationMessage"] = product_result.get("message", "No verification message.")
    checked["lastChecked"] = now_iso()
    checked["linkVerification"] = {
        "product": product_result,
        "datasheet": datasheet_result,
        "checkedAt": checked["lastChecked"],
    }
    if checked.get("unitPrice") and not checked.get("totalPriceEstimate"):
        checked["totalPriceEstimate"] = round(float(checked.get("unitPrice", 0)) + float(checked.get("shippingEstimate", 0)), 2)
    return checked


def web_search_source_candidates(item: dict[str, Any]) -> list[dict[str, Any]]:
    candidates = []
    seen_urls = set()
    for query in make_search_queries(item)[:3]:
        for rank, result in enumerate(fetch_search_results(query), start=1):
            url = result["url"].rstrip("/")
            if url in seen_urls:
                continue
            seen_urls.add(url)
            verified = verify_source_candidate(build_web_candidate(item, result, rank))
            if verified.get("verificationStatus") == "verified":
                candidates.append(verified)
            if len(candidates) >= 2:
                break
        if len(candidates) >= 2:
            break
    return candidates


MOCK_CATALOGUE = [
    {
        "keywords": ["esp32", "microcontroller", "dev board", "wifi"],
        "supplier": "Blockyby Demo Electronics",
        "productName": "ESP32 USB-C Development Board",
        "manufacturer": "DemoParts",
        "manufacturerPartNumber": "DP-ESP32-USBC",
        "supplierPartNumber": "BDE-1001",
        "description": "Low-voltage Wi-Fi/Bluetooth development board for safe electronics prototypes.",
        "productUrl": "demo://supplier/BDE-1001",
        "datasheetUrl": "demo://datasheets/DP-ESP32-USBC",
        "imageUrl": "",
        "unitPrice": 0,
        "currency": "EUR",
        "stockAvailable": 42,
        "minimumOrderQuantity": 1,
        "leadTime": "Demo stock available",
        "verificationStatus": "verified",
        "evidenceNotes": "Matched by board family, low-voltage use, USB-C connector, and common library support.",
    },
    {
        "keywords": ["arduino", "microcontroller", "dev board"],
        "supplier": "Blockyby Demo Electronics",
        "productName": "Arduino-Compatible Starter Board",
        "manufacturer": "DemoParts",
        "manufacturerPartNumber": "DP-ARD-START",
        "supplierPartNumber": "BDE-1004",
        "description": "Beginner-friendly microcontroller board for breadboard prototypes.",
        "productUrl": "demo://supplier/BDE-1004",
        "datasheetUrl": "demo://datasheets/DP-ARD-START",
        "imageUrl": "",
        "unitPrice": 0,
        "currency": "EUR",
        "stockAvailable": 58,
        "minimumOrderQuantity": 1,
        "leadTime": "Demo stock available",
        "verificationStatus": "verified",
        "evidenceNotes": "Matched by requested controller type and beginner-friendly use.",
    },
    {
        "keywords": ["breadboard", "jumper", "wire"],
        "supplier": "Blockyby Demo Electronics",
        "productName": "Breadboard and Jumper Wire Kit",
        "manufacturer": "DemoParts",
        "manufacturerPartNumber": "DP-BB-JUMP",
        "supplierPartNumber": "BDE-1002",
        "description": "Reusable breadboard and jumper kit for temporary circuit prototyping before soldering.",
        "productUrl": "demo://supplier/BDE-1002",
        "datasheetUrl": "",
        "imageUrl": "",
        "unitPrice": 0,
        "currency": "EUR",
        "stockAvailable": 80,
        "minimumOrderQuantity": 1,
        "leadTime": "Demo stock available",
        "verificationStatus": "verified",
        "evidenceNotes": "Matched by prototyping requirement and reversible assembly workflow.",
    },
    {
        "keywords": ["regulated", "power supply", "5v", "usb power"],
        "supplier": "Blockyby Demo Electronics",
        "productName": "5V 2A Regulated USB Power Supply",
        "manufacturer": "DemoPower",
        "manufacturerPartNumber": "DPP-5V-2A",
        "supplierPartNumber": "BDE-1003",
        "description": "Low-voltage regulated supply for small electronics prototypes.",
        "productUrl": "demo://supplier/BDE-1003",
        "datasheetUrl": "demo://datasheets/DPP-5V-2A",
        "imageUrl": "",
        "unitPrice": 0,
        "currency": "EUR",
        "stockAvailable": 31,
        "minimumOrderQuantity": 1,
        "leadTime": "Demo stock available",
        "verificationStatus": "verified",
        "evidenceNotes": "Matched by low-voltage regulated power requirement. User must still check current draw.",
    },
    {
        "keywords": ["pla", "filament", "prototype enclosure", "3d print"],
        "supplier": "Blockyby Demo Maker Supply",
        "productName": "PLA Filament 1.75mm - Warm Ivory",
        "manufacturer": "DemoFilament",
        "manufacturerPartNumber": "DF-PLA-IVORY",
        "supplierPartNumber": "BMS-2001",
        "description": "General-purpose PLA filament for prototype enclosures and brackets.",
        "productUrl": "demo://supplier/BMS-2001",
        "datasheetUrl": "",
        "imageUrl": "",
        "unitPrice": 0,
        "currency": "EUR",
        "stockAvailable": 24,
        "minimumOrderQuantity": 1,
        "leadTime": "Demo stock available",
        "verificationStatus": "verified",
        "evidenceNotes": "Matched by 3D-printable prototype enclosure requirement.",
    },
    {
        "keywords": ["petg", "durable enclosure", "filament"],
        "supplier": "Blockyby Demo Maker Supply",
        "productName": "PETG Filament 1.75mm - Natural",
        "manufacturer": "DemoFilament",
        "manufacturerPartNumber": "DF-PETG-NAT",
        "supplierPartNumber": "BMS-2002",
        "description": "Durable PETG filament for stronger enclosures and brackets.",
        "productUrl": "demo://supplier/BMS-2002",
        "datasheetUrl": "",
        "imageUrl": "",
        "unitPrice": 0,
        "currency": "EUR",
        "stockAvailable": 18,
        "minimumOrderQuantity": 1,
        "leadTime": "Demo stock available",
        "verificationStatus": "verified",
        "evidenceNotes": "Matched by quality-focused enclosure requirement.",
    },
    {
        "keywords": ["m3", "screw", "spacer", "standoff"],
        "supplier": "Blockyby Demo Hardware",
        "productName": "M3 Screw, Spacer, and Standoff Kit",
        "manufacturer": "DemoFixings",
        "manufacturerPartNumber": "DFX-M3-KIT",
        "supplierPartNumber": "BDH-3001",
        "description": "Small metric fastener kit for mounting PCBs and printed assemblies.",
        "productUrl": "demo://supplier/BDH-3001",
        "datasheetUrl": "",
        "imageUrl": "",
        "unitPrice": 0,
        "currency": "EUR",
        "stockAvailable": 71,
        "minimumOrderQuantity": 1,
        "leadTime": "Demo stock available",
        "verificationStatus": "verified",
        "evidenceNotes": "Matched by common PCB/enclosure fastening requirement.",
    },
    {
        "keywords": ["calipers", "digital calipers", "measure"],
        "supplier": "Blockyby Demo Tools",
        "productName": "Digital Calipers 150mm",
        "manufacturer": "DemoMeasure",
        "manufacturerPartNumber": "DM-CAL-150",
        "supplierPartNumber": "BDT-4001",
        "description": "Measuring tool for checking dimensions before CAD and assembly.",
        "productUrl": "demo://supplier/BDT-4001",
        "datasheetUrl": "",
        "imageUrl": "",
        "unitPrice": 0,
        "currency": "EUR",
        "stockAvailable": 16,
        "minimumOrderQuantity": 1,
        "leadTime": "Demo stock available",
        "verificationStatus": "verified",
        "evidenceNotes": "Matched as optional measurement tool for fit verification.",
    },
    {
        "keywords": ["led", "resistor", "assortment"],
        "supplier": "Blockyby Demo Electronics",
        "productName": "LED and Resistor Starter Assortment",
        "manufacturer": "DemoParts",
        "manufacturerPartNumber": "DP-LED-RES",
        "supplierPartNumber": "BDE-1005",
        "description": "Basic indicator LEDs and common resistor values for safe low-voltage tests.",
        "productUrl": "demo://supplier/BDE-1005",
        "datasheetUrl": "",
        "imageUrl": "",
        "unitPrice": 0,
        "currency": "EUR",
        "stockAvailable": 94,
        "minimumOrderQuantity": 1,
        "leadTime": "Demo stock available",
        "verificationStatus": "verified",
        "evidenceNotes": "Matched by visual indicator and electronics debugging requirement.",
    },
    {
        "keywords": ["plywood", "hardwood", "wood board"],
        "supplier": "Blockyby Demo Maker Supply",
        "productName": "Birch Plywood Panel 600x400mm",
        "manufacturer": "DemoWood",
        "manufacturerPartNumber": "DW-PLY-6040",
        "supplierPartNumber": "BMS-2501",
        "description": "Small plywood panel for safe decorative, mounting, and enclosure prototypes.",
        "productUrl": "demo://supplier/BMS-2501",
        "datasheetUrl": "",
        "imageUrl": "",
        "unitPrice": 0,
        "currency": "EUR",
        "stockAvailable": 22,
        "minimumOrderQuantity": 1,
        "leadTime": "Demo stock available",
        "verificationStatus": "verified",
        "evidenceNotes": "Matched by small panel material requirement. Check final dimensions before cutting.",
    },
]


def budget_label(score: int | float | str) -> str:
    try:
        n = float(score)
    except (TypeError, ValueError):
        n = 50
    if n < 30:
        return "cheap-first"
    if n > 70:
        return "best-quality"
    return "balanced"


def text_contains_any(text: str, words: list[str]) -> bool:
    lower = text.lower()
    return any(word.lower() in lower for word in words)


def owned_text(profile: dict[str, Any]) -> str:
    values = []
    for key in ["skills", "tools", "materials", "stock"]:
        value = profile.get(key, [])
        if isinstance(value, list):
            values.extend(str(v) for v in value)
        else:
            values.append(str(value))
    return " ".join(values).lower()


def item_is_owned(profile: dict[str, Any], item_name: str) -> bool:
    owned = owned_text(profile)
    useful_words = [word for word in item_name.lower().replace("-", " ").split() if len(word) > 2]
    return any(word in owned for word in useful_words)


def make_item(profile: dict[str, Any], item: dict[str, Any]) -> dict[str, Any]:
    owned = item_is_owned(profile, item.get("name", ""))
    return {
        "id": item.get("id") or f"part_{uuid4().hex[:8]}",
        "name": item.get("name", "Unnamed item"),
        "category": item.get("category", "general"),
        "required": bool(item.get("required", True)),
        "quantity": float(item.get("quantity", 1)),
        "unitPriceEstimate": float(item.get("unitPriceEstimate", 0)),
        "vendorHint": item.get("vendorHint", "Demo supplier adapter"),
        "ownedAlternative": "Already appears in profile/stock" if owned else item.get("ownedAlternative", "None detected"),
        "compatibilityNotes": item.get("compatibilityNotes", "Check dimensions, ratings, and interface before ordering."),
        "difficulty": item.get("difficulty", "easy"),
        "safetyNotes": item.get("safetyNotes", "Use normal workshop care and age-appropriate supervision."),
        "sourceStatus": "owned" if owned else item.get("sourceStatus", "recommended"),
        "orderable": False if owned else bool(item.get("orderable", True)),
        "selected": False if owned else bool(item.get("selected", True)),
    }


def find_source_candidates(item: dict[str, Any]) -> list[dict[str, Any]]:
    supplier_candidates = supplier_search_source_candidates(item)
    if supplier_candidates:
        return supplier_candidates
    web_candidates = web_search_source_candidates(item)
    if web_candidates:
        return web_candidates

    text = f"{item.get('name', '')} {item.get('category', '')} {item.get('compatibilityNotes', '')}".lower()
    matches = []
    for product in MOCK_CATALOGUE:
        score = sum(1 for keyword in product["keywords"] if keyword in text)
        if score:
            candidate = dict(product)
            candidate["sourceType"] = "demo_catalogue"
            candidate["productUrlVerified"] = False
            candidate["datasheetUrlVerified"] = False
            candidate["verificationStatus"] = "needs_review"
            candidate["verificationMethod"] = "demo_catalogue_fallback"
            candidate["verificationMessage"] = "Live web search did not return a verified result; this demo catalogue candidate is not checkout-ready."
            candidate["unitPrice"] = 0
            candidate["priceText"] = "Demo catalogue fallback has no verified supplier price."
            candidate["priceConfidence"] = "unknown"
            candidate["shippingEstimate"] = 0
            candidate["shippingText"] = "No real shipping quote available for demo catalogue fallback."
            candidate["shippingConfidence"] = "unknown"
            candidate["totalPriceEstimate"] = 0
            candidate["matchScore"] = score
            candidate["lastChecked"] = now_iso()
            matches.append(candidate)
    matches.sort(key=lambda product: product.get("matchScore", 0), reverse=True)
    return matches[:3]


def verify_sourcing_plan(plan: dict[str, Any]) -> dict[str, Any]:
    verified_items = []
    for raw_item in plan.get("items", []):
        item = dict(raw_item)
        if item.get("sourceCandidates"):
            candidates = [verify_source_candidate(dict(candidate)) for candidate in item.get("sourceCandidates", [])]
        else:
            candidates = find_source_candidates(item)
        selected_index = next(
            (index for index, candidate in enumerate(candidates) if candidate.get("verificationStatus") == "verified" and candidate.get("productUrlVerified")),
            -1,
        )
        item["sourceCandidates"] = candidates
        item["selectedSourceIndex"] = selected_index
        item["verificationStatus"] = "verified" if selected_index >= 0 else ("needs_review" if candidates else "unverified")
        if selected_index >= 0:
            selected = candidates[selected_index]
            price_known = selected.get("priceConfidence") == "exact" and float(selected.get("unitPrice", 0) or 0) > 0
            if price_known:
                item["shippingEstimate"] = float(selected.get("shippingEstimate", 0))
                item["totalPriceEstimate"] = float(selected.get("totalPriceEstimate") or selected.get("unitPrice", 0))
                item["pricingStatus"] = "exact"
            else:
                item["shippingEstimate"] = 0
                item["totalPriceEstimate"] = 0
                item["pricingStatus"] = "unknown"
        if item.get("sourceStatus") == "owned":
            item["orderable"] = False
            item["selected"] = False
        elif selected_index < 0:
            item["orderable"] = False
            item["selected"] = False
        verified_items.append(item)

    priced_count = 0
    unknown_price_count = 0
    total = 0
    for item in verified_items:
        if not item.get("orderable") or not item.get("selected", True):
            continue
        if item.get("pricingStatus") == "unknown":
            unknown_price_count += 1
            continue
        priced_count += 1
        candidates = item.get("sourceCandidates") or []
        selected_index = item.get("selectedSourceIndex", -1)
        if selected_index < 0 or selected_index >= len(candidates):
            continue
        selected = candidates[selected_index]
        if selected.get("priceConfidence") == "exact":
            total += float(selected.get("totalPriceEstimate") or selected.get("unitPrice") or 0) * float(item.get("quantity", 1))

    plan["items"] = verified_items
    plan["dataVersion"] = "exact-prices-only-v1"
    plan["estimatedTotal"] = round(total, 2)
    plan["verificationSummary"] = {
        "verifiedCount": sum(1 for item in verified_items if item.get("verificationStatus") == "verified"),
        "unverifiedCount": sum(1 for item in verified_items if item.get("verificationStatus") != "verified"),
        "linksReady": all(
            item.get("verificationStatus") == "verified" or item.get("sourceStatus") == "owned" or not item.get("required", True)
            for item in verified_items
        ),
        "checkoutReady": all(
            item.get("sourceStatus") == "owned"
            or not item.get("required", True)
            or (item.get("verificationStatus") == "verified" and item.get("pricingStatus") == "exact")
            for item in verified_items
        ),
        "sourceMode": "verified supplier/web links with HTTP checks",
        "pricedCount": priced_count,
        "unknownPriceCount": unknown_price_count,
        "pricingNote": "Totals only include exact supplier/API prices. Planning estimates, demo catalogue prices, and search snippets are never shown as product prices.",
    }
    return plan


def fallback_sourcing_plan(profile: dict[str, Any], brief: dict[str, Any], idea: str, budget_quality: int = 50) -> dict[str, Any]:
    label = budget_label(budget_quality)
    text = f"{idea} {brief.get('summary', '')} {brief.get('projectName', '')}".lower()

    is_electronics = text_contains_any(text, ["sensor", "monitor", "arduino", "esp", "raspberry", "led", "robot", "pcb", "circuit", "schematic", "battery", "controller"])
    is_making = text_contains_any(text, ["3d", "cad", "enclosure", "print", "mount", "bracket", "case", "model"])
    is_wood = text_contains_any(text, ["wood", "shelf", "desk", "table", "cabinet", "stand"])

    base = []

    if is_electronics or not (is_making or is_wood):
        base.extend([
            {
                "name": "ESP32 development board" if label != "cheap-first" else "Arduino-compatible microcontroller",
                "category": "electronics",
                "unitPriceEstimate": 0,
                "compatibilityNotes": "Choose one controller family and keep library, voltage, and connector assumptions consistent.",
                "safetyNotes": "Use low-voltage USB-powered prototypes only for the demo flow.",
            },
            {
                "name": "Breadboard and jumper wire kit",
                "category": "electronics",
                "unitPriceEstimate": 0,
                "compatibilityNotes": "Use for the prototype before permanent assembly.",
            },
            {
                "name": "5V regulated power supply",
                "category": "electronics",
                "unitPriceEstimate": 0,
                "compatibilityNotes": "Check current draw and connector compatibility before ordering.",
            },
            {
                "name": "LED and resistor assortment",
                "category": "electronics",
                "unitPriceEstimate": 0,
                "required": False,
                "sourceStatus": "optional",
                "compatibilityNotes": "Useful for status indicators and quick debugging tests.",
            },
        ])

    if is_making or is_electronics:
        base.extend([
            {
                "name": "PLA filament for prototype enclosure" if label != "best-quality" else "PETG filament for durable enclosure",
                "category": "fabrication",
                "unitPriceEstimate": 0,
                "compatibilityNotes": "Check printer material support and expected enclosure temperature.",
            },
            {
                "name": "M3 screw and spacer kit",
                "category": "hardware",
                "unitPriceEstimate": 0,
                "compatibilityNotes": "Confirm hole diameters, board thickness, and enclosure clearance before ordering.",
            },
            {
                "name": "Digital calipers",
                "category": "tool",
                "unitPriceEstimate": 0,
                "required": False,
                "sourceStatus": "optional",
                "compatibilityNotes": "Optional but useful for measuring stock and fixing CAD tolerances.",
            },
        ])

    if is_wood:
        base.extend([
            {
                "name": "Plywood or hardwood board",
                "category": "woodworking",
                "unitPriceEstimate": 0,
                "compatibilityNotes": "Choose thickness based on load and available tools.",
                "verificationStatus": "unverified",
            },
            {
                "name": "Wood screws assortment",
                "category": "hardware",
                "unitPriceEstimate": 0,
                "compatibilityNotes": "Match screw length to board thickness.",
            },
        ])

    items = [make_item(profile, item) for item in base]
    plan = {
        "safe": True,
        "summary": f"Generated a {label} sourcing plan using live web search where available. Each checkout-ready item must have a product URL that passed HTTP verification.",
        "estimatedTotal": 0,
        "currency": "EUR",
        "items": items,
        "existingAssets": [
            {
                "title": "Parametric enclosure starter",
                "type": "CAD template",
                "licenseHint": "Demo asset; replace with real library/source checks.",
                "description": "Placeholder record for an enclosure asset that can be previewed or replaced by a real model.",
                "sourceHint": "Add adapters for project libraries or your own model database.",
                "viewAction": "open-simlab-cad",
            },
            {
                "title": "KiCad footprint review checklist",
                "type": "PCB/schematic support",
                "licenseHint": "Use verified library parts.",
                "description": "Checklist for matching physical parts to schematic symbols and PCB footprints.",
                "sourceHint": "Replace with real EDA library integration later.",
                "viewAction": "open-simlab-schematic",
            },
        ],
        "compatibilityNotes": [
            "Ordering is blocked until required items have verified source candidates.",
            "Planning budget numbers are not product prices and are not shown on supplier cards.",
            "Prices are shown only when an exact supplier/API price is available.",
            "Shipping is unknown unless a supplier/API provides it.",
            "Check voltage, current, connector, footprint, dimensions, software library, and mounting compatibility.",
            "Owned items are useful but still need compatibility checking before assembly.",
        ],
        "sourcingDifficulty": "medium" if len(items) > 6 else "easy",
        "orderWarnings": [
            "Checkout is a safe mock checkout for the hackathon demo.",
            "Real checkout needs supplier APIs, payment processing, tax/shipping logic, returns policy, and privacy review.",
        ],
    }
    return verify_sourcing_plan(plan)


def validate_checkout_items(items: list[dict[str, Any]]) -> tuple[bool, list[str]]:
    problems = []
    for item in items:
        name = item.get("name", "Unknown item")
        if item.get("sourceStatus") == "owned":
            continue
        if item.get("sourceStatus") == "blocked":
            problems.append(f"{name}: item is blocked.")
        if item.get("verificationStatus") != "verified":
            problems.append(f"{name}: no verified source selected.")
        if not item.get("sourceCandidates"):
            problems.append(f"{name}: source candidate list is empty.")
        selected_index = int(item.get("selectedSourceIndex", -1))
        if selected_index < 0:
            problems.append(f"{name}: no source candidate selected.")
            continue
        candidates = item.get("sourceCandidates") or []
        if selected_index >= len(candidates):
            problems.append(f"{name}: selected source index is invalid.")
            continue
        selected = candidates[selected_index]
        if selected.get("verificationStatus") != "verified" or not selected.get("productUrlVerified"):
            problems.append(f"{name}: selected product link did not pass live verification.")
        if not is_http_url(str(selected.get("productUrl", ""))):
            problems.append(f"{name}: selected source has no usable HTTP(S) product link.")
        if selected.get("priceConfidence") != "exact" or float(selected.get("unitPrice", 0) or 0) <= 0:
            problems.append(f"{name}: selected source has no exact supplier/API price yet.")
    return not problems, problems
