from __future__ import annotations

import base64
import os
import re
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


SOURCE_DATABASE_VERSION = "merged-local-exact-plus-live-links-v3"
HTTP_TIMEOUT_SECONDS = float(os.getenv("BLOCKYBY_HTTP_TIMEOUT_SECONDS", "2"))
MAX_WEB_RESULTS_PER_ITEM = int(os.getenv("BLOCKYBY_MAX_WEB_RESULTS_PER_ITEM", "2"))
BLOCKYBY_USER_AGENT = "BlockybyProductSourcingAgent/0.4"

SUPPLIER_HINTS = [
    "digikey", "mouser", "rs-online", "farnell", "element14", "adafruit", "sparkfun",
    "thepihut", "pimoroni", "arduino.cc", "prusa3d", "3djake", "screwfix",
    "toolstation", "diy.com", "pololu", "reichelt", "amazon",
]

BLOCKED_RESULT_HOSTS = {
    "google.com", "duckduckgo.com", "bing.com", "youtube.com", "wikipedia.org", "reddit.com", "pinterest.com",
}

# Local exact-price records keep the demo fully runnable offline. Live supplier/web candidates
# are added as review links, but checkout only uses exact source-card prices.
LOCAL_SOURCE_DATABASE: list[dict[str, Any]] = [{'keywords': ['esp32', 'microcontroller', 'dev board', 'wifi', 'controller'],
  'supplier': 'Blockyby Verified Electronics DB',
  'productName': 'ESP32 USB-C Development Board',
  'manufacturer': 'DemoParts',
  'manufacturerPartNumber': 'DP-ESP32-USBC',
  'supplierPartNumber': 'BDE-1001',
  'description': 'Low-voltage Wi-Fi/Bluetooth development board for safe electronics prototypes.',
  'productUrl': '',
  'datasheetUrl': '',
  'imageUrl': '',
  'unitPrice': 9.5,
  'currency': 'EUR',
  'stockAvailable': 42,
  'minimumOrderQuantity': 1,
  'leadTime': 'Demo stock available',
  'evidenceNotes': 'Matched by controller family, low-voltage use, USB-C connector, and common hobby library '
                   'support.'},
 {'keywords': ['arduino', 'microcontroller', 'dev board', 'starter board'],
  'supplier': 'Blockyby Verified Electronics DB',
  'productName': 'Arduino-Compatible Starter Board',
  'manufacturer': 'DemoParts',
  'manufacturerPartNumber': 'DP-ARD-START',
  'supplierPartNumber': 'BDE-1004',
  'description': 'Beginner-friendly microcontroller board for breadboard prototypes.',
  'productUrl': '',
  'datasheetUrl': '',
  'imageUrl': '',
  'unitPrice': 8.25,
  'currency': 'EUR',
  'stockAvailable': 58,
  'minimumOrderQuantity': 1,
  'leadTime': 'Demo stock available',
  'evidenceNotes': 'Matched by requested controller type and beginner-friendly prototyping use.'},
 {'keywords': ['breadboard', 'jumper', 'wire', 'prototype'],
  'supplier': 'Blockyby Verified Electronics DB',
  'productName': 'Breadboard and Jumper Wire Kit',
  'manufacturer': 'DemoParts',
  'manufacturerPartNumber': 'DP-BB-JUMP',
  'supplierPartNumber': 'BDE-1002',
  'description': 'Reusable breadboard and jumper kit for temporary circuit prototyping before soldering.',
  'productUrl': '',
  'datasheetUrl': '',
  'imageUrl': '',
  'unitPrice': 7.0,
  'currency': 'EUR',
  'stockAvailable': 80,
  'minimumOrderQuantity': 1,
  'leadTime': 'Demo stock available',
  'evidenceNotes': 'Matched by reversible assembly workflow and prototype wiring requirement.'},
 {'keywords': ['regulated', 'power supply', '5v', 'usb power'],
  'supplier': 'Blockyby Verified Electronics DB',
  'productName': '5V 2A Regulated USB Power Supply',
  'manufacturer': 'DemoPower',
  'manufacturerPartNumber': 'DPP-5V-2A',
  'supplierPartNumber': 'BDE-1003',
  'description': 'Low-voltage regulated supply for small electronics prototypes.',
  'productUrl': '',
  'datasheetUrl': '',
  'imageUrl': '',
  'unitPrice': 8.75,
  'currency': 'EUR',
  'stockAvailable': 31,
  'minimumOrderQuantity': 1,
  'leadTime': 'Demo stock available',
  'evidenceNotes': 'Matched by low-voltage regulated power requirement. User must still check current draw.'},
 {'keywords': ['pla', 'filament', 'prototype enclosure', '3d print', 'enclosure'],
  'supplier': 'Blockyby Verified Maker DB',
  'productName': 'PLA Filament 1.75mm - Warm Ivory',
  'manufacturer': 'DemoFilament',
  'manufacturerPartNumber': 'DF-PLA-IVORY',
  'supplierPartNumber': 'BMS-2001',
  'description': 'General-purpose PLA filament for prototype enclosures and brackets.',
  'productUrl': '',
  'datasheetUrl': '',
  'imageUrl': '',
  'unitPrice': 18.0,
  'currency': 'EUR',
  'stockAvailable': 24,
  'minimumOrderQuantity': 1,
  'leadTime': 'Demo stock available',
  'evidenceNotes': 'Matched by 3D-printable prototype enclosure requirement.'},
 {'keywords': ['petg', 'durable enclosure', 'filament'],
  'supplier': 'Blockyby Verified Maker DB',
  'productName': 'PETG Filament 1.75mm - Natural',
  'manufacturer': 'DemoFilament',
  'manufacturerPartNumber': 'DF-PETG-NAT',
  'supplierPartNumber': 'BMS-2002',
  'description': 'Durable PETG filament for stronger enclosures and brackets.',
  'productUrl': '',
  'datasheetUrl': '',
  'imageUrl': '',
  'unitPrice': 27.5,
  'currency': 'EUR',
  'stockAvailable': 18,
  'minimumOrderQuantity': 1,
  'leadTime': 'Demo stock available',
  'evidenceNotes': 'Matched by quality-focused enclosure requirement.'},
 {'keywords': ['m3', 'screw', 'spacer', 'standoff', 'mounting'],
  'supplier': 'Blockyby Verified Hardware DB',
  'productName': 'M3 Screw, Spacer, and Standoff Kit',
  'manufacturer': 'DemoFixings',
  'manufacturerPartNumber': 'DFX-M3-KIT',
  'supplierPartNumber': 'BDH-3001',
  'description': 'Small metric fastener kit for mounting PCBs and printed assemblies.',
  'productUrl': '',
  'datasheetUrl': '',
  'imageUrl': '',
  'unitPrice': 8.0,
  'currency': 'EUR',
  'stockAvailable': 71,
  'minimumOrderQuantity': 1,
  'leadTime': 'Demo stock available',
  'evidenceNotes': 'Matched by common PCB/enclosure fastening requirement.'},
 {'keywords': ['calipers', 'digital calipers', 'measure', 'measurement'],
  'supplier': 'Blockyby Verified Tools DB',
  'productName': 'Digital Calipers 150mm',
  'manufacturer': 'DemoMeasure',
  'manufacturerPartNumber': 'DM-CAL-150',
  'supplierPartNumber': 'BDT-4001',
  'description': 'Measuring tool for checking dimensions before CAD and assembly.',
  'productUrl': '',
  'datasheetUrl': '',
  'imageUrl': '',
  'unitPrice': 12.0,
  'currency': 'EUR',
  'stockAvailable': 16,
  'minimumOrderQuantity': 1,
  'leadTime': 'Demo stock available',
  'evidenceNotes': 'Matched as optional measurement tool for fit verification.'},
 {'keywords': ['led', 'resistor', 'assortment', 'indicator'],
  'supplier': 'Blockyby Verified Electronics DB',
  'productName': 'LED and Resistor Starter Assortment',
  'manufacturer': 'DemoParts',
  'manufacturerPartNumber': 'DP-LED-RES',
  'supplierPartNumber': 'BDE-1005',
  'description': 'Basic indicator LEDs and common resistor values for safe low-voltage tests.',
  'productUrl': '',
  'datasheetUrl': '',
  'imageUrl': '',
  'unitPrice': 6.0,
  'currency': 'EUR',
  'stockAvailable': 94,
  'minimumOrderQuantity': 1,
  'leadTime': 'Demo stock available',
  'evidenceNotes': 'Matched by visual indicator and electronics debugging requirement.'},
 {'keywords': ['plywood', 'hardwood', 'wood board', 'board'],
  'supplier': 'Blockyby Verified Maker DB',
  'productName': 'Birch Plywood Panel 600x400mm',
  'manufacturer': 'DemoWood',
  'manufacturerPartNumber': 'DW-PLY-6040',
  'supplierPartNumber': 'BMS-2501',
  'description': 'Small plywood panel for decorative, mounting, and enclosure prototypes.',
  'productUrl': '',
  'datasheetUrl': '',
  'imageUrl': '',
  'unitPrice': 14.0,
  'currency': 'EUR',
  'stockAvailable': 22,
  'minimumOrderQuantity': 1,
  'leadTime': 'Demo stock available',
  'evidenceNotes': 'Matched by small panel material requirement. Check final dimensions before cutting.'},
 {'keywords': ['wood screws', 'wood screw', 'screws assortment', 'woodworking'],
  'supplier': 'Blockyby Verified Hardware DB',
  'productName': 'Wood Screws Assortment',
  'manufacturer': 'DemoFixings',
  'manufacturerPartNumber': 'DFX-WOOD-SCREWS',
  'supplierPartNumber': 'BDH-3002',
  'description': 'Mixed wood screws for small safe workshop projects.',
  'productUrl': '',
  'datasheetUrl': '',
  'imageUrl': '',
  'unitPrice': 6.0,
  'currency': 'EUR',
  'stockAvailable': 44,
  'minimumOrderQuantity': 1,
  'leadTime': 'Demo stock available',
  'evidenceNotes': 'Matched by wood fastening requirement. Confirm screw length against board thickness.'},
 {'keywords': ['moisture', 'soil', 'plant sensor', 'capacitive sensor', 'garden sensor'],
  'supplier': 'Blockyby Verified Electronics DB',
  'productName': 'Capacitive Soil Moisture Sensor Module',
  'manufacturer': 'DemoParts',
  'manufacturerPartNumber': 'DP-SOIL-CAP',
  'supplierPartNumber': 'BDE-1010',
  'description': 'Low-voltage capacitive moisture sensor for plant-monitor prototypes.',
  'productUrl': '',
  'datasheetUrl': '',
  'imageUrl': '',
  'unitPrice': 4.75,
  'currency': 'EUR',
  'stockAvailable': 63,
  'minimumOrderQuantity': 1,
  'leadTime': 'Demo stock available',
  'evidenceNotes': 'Matched by plant/garden monitoring requirement and low-voltage sensor use. Keep probes '
                   'away from mains wiring.'},
 {'keywords': ['oled', 'display', 'screen', 'i2c'],
  'supplier': 'Blockyby Verified Electronics DB',
  'productName': '0.96 inch I2C OLED Display Module',
  'manufacturer': 'DemoParts',
  'manufacturerPartNumber': 'DP-OLED-096',
  'supplierPartNumber': 'BDE-1011',
  'description': 'Small low-voltage display module for status screens and quick debugging.',
  'productUrl': '',
  'datasheetUrl': '',
  'imageUrl': '',
  'unitPrice': 6.5,
  'currency': 'EUR',
  'stockAvailable': 47,
  'minimumOrderQuantity': 1,
  'leadTime': 'Demo stock available',
  'evidenceNotes': 'Matched by display/status-output requirement. Check I2C voltage and library '
                   'compatibility.'},
 {'keywords': ['servo', 'motor', 'robot', 'actuator', 'pan tilt'],
  'supplier': 'Blockyby Verified Robotics DB',
  'productName': 'Micro Servo Motor 9g',
  'manufacturer': 'DemoMotion',
  'manufacturerPartNumber': 'DM-SERVO-9G',
  'supplierPartNumber': 'BDR-5001',
  'description': 'Small hobby servo for low-load robotics movement demonstrations.',
  'productUrl': '',
  'datasheetUrl': '',
  'imageUrl': '',
  'unitPrice': 5.25,
  'currency': 'EUR',
  'stockAvailable': 38,
  'minimumOrderQuantity': 1,
  'leadTime': 'Demo stock available',
  'evidenceNotes': 'Matched by low-load motion requirement. Use a suitable low-voltage supply and test '
                   'without load first.'},
 {'keywords': ['temperature', 'humidity', 'environment', 'dht', 'bme280'],
  'supplier': 'Blockyby Verified Electronics DB',
  'productName': 'Temperature and Humidity Sensor Module',
  'manufacturer': 'DemoParts',
  'manufacturerPartNumber': 'DP-ENV-SENSOR',
  'supplierPartNumber': 'BDE-1012',
  'description': 'Low-voltage environmental sensor for room, garden, or enclosure-monitoring builds.',
  'productUrl': '',
  'datasheetUrl': '',
  'imageUrl': '',
  'unitPrice': 5.95,
  'currency': 'EUR',
  'stockAvailable': 52,
  'minimumOrderQuantity': 1,
  'leadTime': 'Demo stock available',
  'evidenceNotes': 'Matched by environment-monitoring requirement. Confirm library and voltage support '
                   'before assembly.'}]


class DuckDuckGoResultParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.results: list[dict[str, str]] = []
        self._current: dict[str, str] | None = None
        self._field: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = dict(attrs)
        classes = set((attr.get("class") or "").split())
        if tag == "a" and "result__a" in classes:
            self._current = {"title": "", "url": clean_duckduckgo_url(attr.get("href") or ""), "snippet": ""}
            self._field = "title"
        elif self._current is not None and tag in {"a", "div"} and ("result__snippet" in classes or "result__body" in classes):
            self._field = "snippet"

    def handle_endtag(self, tag: str) -> None:
        if self._current and tag == "a" and self._field == "title":
            self._field = None
        if self._current and tag == "div" and self._current.get("title") and self._current.get("url"):
            self.results.append(self._current)
            self._current = None
            self._field = None

    def handle_data(self, data: str) -> None:
        if self._current is not None and self._field:
            self._current[self._field] = compact_text(self._current.get(self._field, "") + " " + data)


def env_enabled(name: str, default: str = "0") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


def compact_text(value: Any) -> str:
    return re.sub(r"\s+", " ", unescape(str(value or ""))).strip()


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


def is_http_url(url: str) -> bool:
    parsed = urlparse(str(url or ""))
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def clean_duckduckgo_url(url: str) -> str:
    parsed = urlparse(url)
    if "duckduckgo.com" in parsed.netloc and parsed.path.startswith("/l/"):
        target = parse_qs(parsed.query).get("uddg", [""])[0]
        if target:
            return unquote(target)
    return url


def clean_bing_url(url: str) -> str:
    parsed = urlparse(unescape(url))
    if "bing.com" in parsed.netloc and parsed.path.startswith("/ck/a"):
        target = parse_qs(parsed.query).get("u", [""])[0]
        if target.startswith("a1"):
            try:
                padded = target[2:] + "=" * (-len(target[2:]) % 4)
                return base64.urlsafe_b64decode(padded.encode()).decode("utf-8", errors="ignore")
            except Exception:
                return url
    return unescape(url)


def host_is_useful_product_source(url: str) -> bool:
    host = urlparse(url).netloc.lower().removeprefix("www.")
    if not host or any(host == blocked or host.endswith("." + blocked) for blocked in BLOCKED_RESULT_HOSTS):
        return False
    return any(hint in host for hint in SUPPLIER_HINTS)


def supplier_name_from_url(url: str) -> str:
    host = urlparse(url).netloc.lower().removeprefix("www.")
    if not host:
        return "Unknown supplier"
    parts = [part for part in host.split(".") if part not in {"ie", "uk", "com", "co", "store", "en", "www"}]
    name = (parts[0] if parts else host.split(".")[0]).replace("-", " ").replace("_", " ")
    return name.title()


def safe_request(url: str, method: str = "GET") -> Request:
    return Request(
        url,
        method=method,
        headers={"User-Agent": BLOCKYBY_USER_AGENT, "Accept": "text/html,application/xhtml+xml"},
    )


def probe_url(url: str) -> dict[str, Any]:
    if not is_http_url(url):
        return {"url": url, "ok": False, "statusCode": None, "message": "Missing or non-HTTP(S) URL."}
    if not env_enabled("BLOCKYBY_LIVE_LINK_CHECKS", "0"):
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


def extract_html_text(html: str) -> str:
    text = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.I)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    return compact_text(text)


def fetch_bing_search_results(query: str, limit: int) -> list[dict[str, str]]:
    if not env_enabled("BLOCKYBY_WEB_SEARCH", "0"):
        return []
    url = f"https://www.bing.com/search?q={quote_plus(query)}"
    try:
        with urlopen(safe_request(url), timeout=HTTP_TIMEOUT_SECONDS) as response:
            html = response.read(700_000).decode("utf-8", errors="replace")
    except (TimeoutError, URLError, OSError):
        return []
    results: list[dict[str, str]] = []
    chunks = re.split(r'<li[^>]*class="[^"]*\bb_algo\b[^"]*"[^>]*>', html, flags=re.I)
    for chunk in chunks[1:]:
        chunk = chunk.split("</li>", 1)[0]
        link = re.search(r'<a[^>]*href="([^"]+)"[^>]*>([\s\S]*?)</a>', chunk, flags=re.I)
        if not link:
            continue
        product_url = clean_bing_url(link.group(1))
        if not is_http_url(product_url) or not host_is_useful_product_source(product_url):
            continue
        snippet_match = re.search(r'<p[^>]*>([\s\S]*?)</p>', chunk, flags=re.I)
        results.append({
            "title": extract_html_text(link.group(2)),
            "url": product_url,
            "snippet": extract_html_text(snippet_match.group(1) if snippet_match else ""),
        })
        if len(results) >= limit:
            break
    return results


def fetch_duckduckgo_search_results(query: str, limit: int) -> list[dict[str, str]]:
    if not env_enabled("BLOCKYBY_WEB_SEARCH", "0"):
        return []
    url = f"https://duckduckgo.com/html/?q={quote_plus(query)}"
    try:
        with urlopen(safe_request(url), timeout=HTTP_TIMEOUT_SECONDS) as response:
            html = response.read(700_000).decode("utf-8", errors="replace")
    except (TimeoutError, URLError, OSError):
        return []
    parser = DuckDuckGoResultParser()
    parser.feed(html)
    deduped: list[dict[str, str]] = []
    seen: set[str] = set()
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


@lru_cache(maxsize=256)
def cached_search_results(query: str, limit: int) -> tuple[tuple[str, str, str], ...]:
    results = fetch_bing_search_results(query, limit) or fetch_duckduckgo_search_results(query, limit)
    return tuple((result["title"], result["url"], result["snippet"]) for result in results)


def fetch_search_results(query: str, limit: int = MAX_WEB_RESULTS_PER_ITEM) -> list[dict[str, str]]:
    return [{"title": title, "url": url, "snippet": snippet} for title, url, snippet in cached_search_results(query, limit)]


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
            ("Screwfix", f"https://www.screwfix.ie/search?search={query}"),
            ("Toolstation", f"https://www.toolstation.ie/search?q={query}"),
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


def source_search_url(item: dict[str, Any]) -> str:
    urls = supplier_search_urls_for_item(item)
    return urls[0][1] if urls else ""


def build_web_candidate(item: dict[str, Any], result: dict[str, str], rank: int) -> dict[str, Any]:
    product_url = result["url"]
    return {
        "supplier": supplier_name_from_url(product_url),
        "productName": (result.get("title") or item.get("name") or "Product result")[:160],
        "manufacturer": "",
        "manufacturerPartNumber": "",
        "supplierPartNumber": "",
        "description": (result.get("snippet") or f"Web result for {item.get('name', 'requested item')}.")[:360],
        "productUrl": product_url,
        "datasheetUrl": "",
        "imageUrl": "",
        "unitPrice": 0,
        "currency": "EUR",
        "priceText": "Exact supplier/API price not available from search result.",
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
        "evidenceNotes": "Found by optional live web search. Search snippets are not trusted for prices.",
    }


def verify_source_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    checked = dict(candidate)
    product_result = probe_url(str(checked.get("productUrl", "")))
    datasheet_url = str(checked.get("datasheetUrl", ""))
    datasheet_result = probe_url(datasheet_url) if datasheet_url else {"url": "", "ok": False, "statusCode": None, "message": "No datasheet URL supplied."}
    product_ok = bool(product_result.get("ok"))
    checked["productUrl"] = product_result.get("url") or checked.get("productUrl", "")
    checked["productUrlVerified"] = product_ok
    checked["datasheetUrlVerified"] = bool(datasheet_url) and bool(datasheet_result.get("ok"))
    checked["verificationStatus"] = "verified" if product_ok else checked.get("verificationStatus", "needs_review")
    checked["verificationMethod"] = "live_http_probe" if env_enabled("BLOCKYBY_LIVE_LINK_CHECKS", "0") else "review_link_template"
    checked["verificationMessage"] = product_result.get("message", "No verification message.")
    checked["lastChecked"] = now_iso()
    checked["linkVerification"] = {"product": product_result, "datasheet": datasheet_result, "checkedAt": checked["lastChecked"]}
    return checked


def supplier_search_source_candidates(item: dict[str, Any]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for rank, (supplier, url) in enumerate(supplier_search_urls_for_item(item), start=1):
        candidate = {
            "supplier": supplier,
            "productName": f"{supplier} search for {item.get('name', 'part')}",
            "manufacturer": "",
            "manufacturerPartNumber": "",
            "supplierPartNumber": "",
            "description": "Supplier search page. Open it to choose a concrete product and confirm final price, stock, and shipping.",
            "productUrl": url,
            "datasheetUrl": "",
            "imageUrl": "",
            "unitPrice": 0,
            "currency": "EUR",
            "priceText": "Unknown until a specific supplier product/API price is selected.",
            "priceConfidence": "unknown",
            "shippingEstimate": 0,
            "shippingText": "Unknown until checkout or supplier delivery information is available.",
            "shippingConfidence": "unknown",
            "totalPriceEstimate": 0,
            "stockAvailable": None,
            "minimumOrderQuantity": 1,
            "leadTime": "Check supplier page",
            "sourceType": "supplier_search",
            "matchScore": max(1, 5 - rank),
            "evidenceNotes": "Generated from a trusted supplier search URL template. It is a review link, not a checkout-ready price.",
            "sourceSearchUrl": url,
            "verificationStatus": "needs_review",
            "verificationMethod": "supplier_search_template",
            "verificationMessage": "Open the supplier search page and pick a specific product before real checkout.",
            "productUrlVerified": False,
            "datasheetUrlVerified": False,
            "lastChecked": now_iso(),
        }
        if env_enabled("BLOCKYBY_LIVE_LINK_CHECKS", "0"):
            candidate = verify_source_candidate(candidate)
        candidates.append(candidate)
        if len(candidates) >= 2:
            break
    return candidates


def web_search_source_candidates(item: dict[str, Any]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    for query in make_search_queries(item)[:3]:
        for rank, result in enumerate(fetch_search_results(query), start=1):
            url = result["url"].rstrip("/")
            if url in seen_urls:
                continue
            seen_urls.add(url)
            candidate = verify_source_candidate(build_web_candidate(item, result, rank))
            candidates.append(candidate)
            if len(candidates) >= 2:
                break
        if len(candidates) >= 2:
            break
    return candidates


def owned_text(profile: dict[str, Any]) -> str:
    values: list[str] = []
    for key in ["skills", "tools", "materials", "stock"]:
        value = profile.get(key, [])
        if isinstance(value, list):
            values.extend(str(v) for v in value)
        else:
            values.append(str(value))
    return " ".join(values).lower()


GENERIC_OWNED_WORDS = {
    "and", "the", "kit", "module", "board", "development", "starter", "assortment",
    "prototype", "optional", "digital", "regulated", "supply", "power", "display", "inch",
    "sensor", "wood", "screw", "screws", "spacer", "spacers", "standoff", "standoffs",
}

OWNED_PHRASES = [
    "breadboard", "jumper wire", "jumper wires", "pla filament", "petg filament",
    "m3 screw", "m3 screws", "led", "leds", "resistor", "resistors",
    "digital caliper", "digital calipers", "caliper", "calipers",
]


def normalized_tokens(text: str) -> set[str]:
    tokens = set(re.findall(r"[a-z0-9]+", text.lower()))
    tokens.update(token[:-1] for token in list(tokens) if token.endswith("s") and len(token) > 3)
    return tokens


def item_is_owned(profile: dict[str, Any], item_name: str) -> bool:
    owned = owned_text(profile).lower()
    name = item_name.lower()
    owned_tokens = normalized_tokens(owned)
    name_tokens = normalized_tokens(name)
    for phrase in OWNED_PHRASES:
        phrase_tokens = normalized_tokens(phrase)
        if phrase_tokens and phrase_tokens <= name_tokens and phrase_tokens <= owned_tokens:
            return True
    item_tokens = [token for token in name_tokens if len(token) > 2 and token not in GENERIC_OWNED_WORDS]
    if not item_tokens:
        return False
    matched = sum(1 for token in item_tokens if token in owned_tokens)
    if len(item_tokens) == 1:
        return matched == 1
    return matched >= min(2, len(item_tokens))


def make_item(profile: dict[str, Any], item: dict[str, Any]) -> dict[str, Any]:
    owned = item_is_owned(profile, item.get("name", ""))
    return {
        "id": item.get("id") or f"part_{uuid4().hex[:8]}",
        "name": compact_text(item.get("name", "Unnamed item")),
        "category": compact_text(item.get("category", "general")),
        "required": bool(item.get("required", True)),
        "quantity": float(item.get("quantity", 1)),
        "unitPriceEstimate": float(item.get("unitPriceEstimate", 0)),
        "vendorHint": item.get("vendorHint", "Local exact catalogue plus supplier search"),
        "ownedAlternative": "Already appears in profile/stock" if owned else item.get("ownedAlternative", "None detected"),
        "compatibilityNotes": item.get("compatibilityNotes", "Check dimensions, ratings, and interface before ordering."),
        "difficulty": item.get("difficulty", "easy"),
        "safetyNotes": item.get("safetyNotes", "Use normal workshop care and age-appropriate supervision."),
        "sourceStatus": "owned" if owned else item.get("sourceStatus", "recommended"),
        "orderable": False if owned else bool(item.get("orderable", True)),
        "selected": False if owned else bool(item.get("selected", True)),
    }


def build_source_candidate(product: dict[str, Any], score: int, item: dict[str, Any] | None = None) -> dict[str, Any]:
    unit = float(product.get("unitPrice", 0) or 0)
    shipping = float(product.get("shippingEstimate", 0) or 0)
    search_url = product.get("sourceSearchUrl") or (source_search_url(item or {}) if item else "")
    candidate = dict(product)
    candidate.update({
        "sourceType": "local_source_database",
        "verificationStatus": "verified",
        "verificationMethod": "curated_local_catalogue",
        "verificationMessage": "Exact demo price verified against the local hackathon source database.",
        "productUrlVerified": False,
        "datasheetUrlVerified": bool(product.get("datasheetUrl")),
        "priceText": f"{product.get('currency', 'EUR')} {unit:.2f}",
        "priceConfidence": "exact",
        "shippingEstimate": shipping,
        "shippingText": "Shipping is not included in the hackathon mock checkout.",
        "shippingConfidence": "not_included",
        "totalPriceEstimate": round(unit + shipping, 2),
        "stockAvailable": product.get("stockAvailable"),
        "matchScore": score,
        "lastChecked": now_iso(),
        "sourceSearchUrl": search_url,
        "linkVerification": {
            "product": {"ok": False, "message": "Local exact-price record; use the supplier search link for real product review."},
            "checkedAt": now_iso(),
        },
    })
    return candidate


GENERIC_SOURCE_KEYWORDS = {
    "board", "module", "kit", "assortment", "starter", "prototype", "controller",
    "enclosure", "indicator", "measure", "measurement", "mounting", "screen",
}


def keyword_match_score(keyword: str, name_text: str, full_text: str) -> int:
    key = keyword.lower().strip()
    if not key or key in GENERIC_SOURCE_KEYWORDS:
        return 0
    if " " in key:
        if key in name_text:
            return 3
        if key in full_text:
            return 1
        return 0
    if key in normalized_tokens(name_text):
        return 2
    if key in normalized_tokens(full_text):
        return 1
    return 0


def local_source_candidates(item: dict[str, Any]) -> list[dict[str, Any]]:
    name_text = f"{item.get('name', '')} {item.get('category', '')}".lower()
    full_text = f"{item.get('name', '')} {item.get('category', '')} {item.get('compatibilityNotes', '')}".lower()
    matches: list[dict[str, Any]] = []
    for product in LOCAL_SOURCE_DATABASE:
        score = sum(keyword_match_score(keyword, name_text, full_text) for keyword in product["keywords"])
        if score > 0:
            matches.append(build_source_candidate(product, score, item))
    matches.sort(key=lambda product: product.get("matchScore", 0), reverse=True)
    return matches[:3]


def dedupe_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = "|".join([
            str(candidate.get("sourceType", "")),
            str(candidate.get("supplierPartNumber") or candidate.get("productUrl") or candidate.get("productName", "")),
        ]).lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(candidate)
    return deduped


def find_source_candidates(item: dict[str, Any]) -> list[dict[str, Any]]:
    candidates = local_source_candidates(item)
    candidates.extend(web_search_source_candidates(item))
    candidates.extend(supplier_search_source_candidates(item))
    return dedupe_candidates(candidates)[:6]


def selected_source_for_item(item: dict[str, Any]) -> dict[str, Any]:
    selected_index = int(item.get("selectedSourceIndex", -1))
    candidates = item.get("sourceCandidates") or []
    if selected_index < 0 or selected_index >= len(candidates):
        return {}
    return candidates[selected_index]


def line_total_from_source(item: dict[str, Any]) -> float:
    source = selected_source_for_item(item)
    if source.get("priceConfidence") != "exact":
        return 0
    unit_total = float(source.get("totalPriceEstimate") or source.get("unitPrice") or 0)
    return round(unit_total * float(item.get("quantity", 1) or 1), 2)


def verify_sourcing_plan(plan: dict[str, Any]) -> dict[str, Any]:
    verified_items: list[dict[str, Any]] = []
    for raw_item in plan.get("items", []):
        item = dict(raw_item)
        if item.get("sourceStatus") == "owned":
            candidates = []
        else:
            # Always refresh candidates so saved or LLM-drafted plans get the merged local/live source logic.
            candidates = find_source_candidates(item)

        selected_index = next(
            (
                index
                for index, candidate in enumerate(candidates)
                if candidate.get("verificationStatus") == "verified" and candidate.get("priceConfidence") == "exact"
            ),
            -1,
        )

        item["sourceCandidates"] = candidates
        item["selectedSourceIndex"] = selected_index
        item["verificationStatus"] = "verified" if selected_index >= 0 else ("needs_review" if candidates else "unverified")

        if selected_index >= 0:
            selected = candidates[selected_index]
            item["pricingStatus"] = selected.get("priceConfidence", "unknown")
            item["shippingEstimate"] = float(selected.get("shippingEstimate", 0) or 0)
            item["totalPriceEstimate"] = float(selected.get("totalPriceEstimate") or selected.get("unitPrice", 0) or 0)
        else:
            item["pricingStatus"] = "unknown"
            item["shippingEstimate"] = 0
            item["totalPriceEstimate"] = 0

        if item.get("sourceStatus") == "owned":
            item["orderable"] = False
            item["selected"] = False
        elif selected_index < 0:
            item["orderable"] = False
            item["selected"] = False

        verified_items.append(item)

    selected_orderable = [item for item in verified_items if item.get("orderable") and item.get("selected", True)]
    plan["items"] = verified_items
    plan["dataVersion"] = SOURCE_DATABASE_VERSION
    plan["estimatedTotal"] = round(sum(line_total_from_source(item) for item in selected_orderable), 2)
    source_required_items = [
        item for item in verified_items
        if item.get("sourceStatus") != "owned" and item.get("required", True)
    ]
    owned_count = sum(1 for item in verified_items if item.get("sourceStatus") == "owned")
    plan["verificationSummary"] = {
        "verifiedCount": sum(1 for item in source_required_items if item.get("verificationStatus") == "verified"),
        "unverifiedCount": sum(1 for item in source_required_items if item.get("verificationStatus") != "verified"),
        "ownedCount": owned_count,
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
        "sourceMode": "local exact catalogue + supplier search links + optional live web verification",
        "pricedCount": sum(1 for item in selected_orderable if item.get("pricingStatus") == "exact"),
        "unknownPriceCount": sum(1 for item in selected_orderable if item.get("pricingStatus") != "exact"),
        "pricingNote": "Mock checkout totals use exact selected source-card prices only. Supplier search and web-search links are review aids, not price evidence.",
    }
    return plan


def fallback_sourcing_plan(profile: dict[str, Any], brief: dict[str, Any], idea: str, budget_quality: int = 50) -> dict[str, Any]:
    label = budget_label(budget_quality)
    text = f"{idea} {brief.get('summary', '')} {brief.get('projectName', '')}".lower()

    is_electronics = text_contains_any(text, ["sensor", "monitor", "arduino", "esp", "raspberry", "led", "robot", "pcb", "circuit", "schematic", "battery", "controller", "plant", "garden"])
    is_making = text_contains_any(text, ["3d", "cad", "enclosure", "print", "mount", "bracket", "case", "model"])
    is_wood = text_contains_any(text, ["wood", "wooden", "plywood", "hardwood", "shelf", "cabinet", "woodworking"])
    is_plant = text_contains_any(text, ["plant", "soil", "moisture", "garden"])
    wants_display = text_contains_any(text, ["display", "screen", "oled", "status"])
    wants_motion = text_contains_any(text, ["robot", "servo", "motor", "actuator", "pan", "tilt"])
    wants_environment = text_contains_any(text, ["temperature", "humidity", "environment", "weather"])

    base: list[dict[str, Any]] = []

    if is_electronics or not (is_making or is_wood):
        base.extend([
            {
                "name": "ESP32 development board" if label != "cheap-first" else "Arduino-compatible microcontroller",
                "category": "electronics",
                "unitPriceEstimate": 9.50 if label != "cheap-first" else 8.25,
                "compatibilityNotes": "Choose one controller family and keep library, voltage, and connector assumptions consistent.",
                "safetyNotes": "Use low-voltage USB-powered prototypes only for the demo flow.",
            },
            {
                "name": "Breadboard and jumper wire kit",
                "category": "electronics",
                "unitPriceEstimate": 7.00,
                "compatibilityNotes": "Use for the prototype before permanent assembly.",
            },
            {
                "name": "5V regulated power supply",
                "category": "electronics",
                "unitPriceEstimate": 8.75,
                "compatibilityNotes": "Check current draw and connector compatibility before ordering.",
            },
        ])
        if is_plant:
            base.append({
                "name": "Capacitive soil moisture sensor module",
                "category": "electronics",
                "unitPriceEstimate": 4.75,
                "compatibilityNotes": "Confirm controller voltage, calibration range, connector style, and waterproofing plan before use.",
            })
        if wants_environment:
            base.append({
                "name": "Temperature and humidity sensor module",
                "category": "electronics",
                "unitPriceEstimate": 5.95,
                "required": False,
                "sourceStatus": "optional",
                "compatibilityNotes": "Useful when the project needs environment context. Check voltage and library support.",
            })
        if wants_display:
            base.append({
                "name": "0.96 inch I2C OLED display module",
                "category": "electronics",
                "unitPriceEstimate": 6.50,
                "required": False,
                "sourceStatus": "optional",
                "compatibilityNotes": "Optional status screen. Check I2C address, voltage, and library compatibility.",
            })
        if wants_motion:
            base.append({
                "name": "Micro servo motor 9g",
                "category": "electronics",
                "unitPriceEstimate": 5.25,
                "compatibilityNotes": "Use only for low-load demo motion and test movement without load first.",
            })
        base.append({
            "name": "LED and resistor assortment",
            "category": "electronics",
            "unitPriceEstimate": 6.00,
            "required": False,
            "sourceStatus": "optional",
            "compatibilityNotes": "Useful for status indicators and quick debugging tests.",
        })

    if is_making or is_electronics:
        base.extend([
            {
                "name": "PLA filament for prototype enclosure" if label != "best-quality" else "PETG filament for durable enclosure",
                "category": "fabrication",
                "unitPriceEstimate": 18.00 if label != "best-quality" else 27.50,
                "compatibilityNotes": "Check printer material support and expected enclosure temperature.",
            },
            {
                "name": "M3 screw and spacer kit",
                "category": "hardware",
                "unitPriceEstimate": 8.00,
                "compatibilityNotes": "Confirm hole diameters, board thickness, and enclosure clearance before ordering.",
            },
            {
                "name": "Digital calipers",
                "category": "tool",
                "unitPriceEstimate": 12.00,
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
                "unitPriceEstimate": 14.00,
                "compatibilityNotes": "Choose thickness based on load and available tools.",
            },
            {
                "name": "Wood screws assortment",
                "category": "hardware",
                "unitPriceEstimate": 6.00,
                "compatibilityNotes": "Match screw length to board thickness.",
            },
        ])

    items = [make_item(profile, item) for item in base]
    plan = {
        "safe": True,
        "summary": f"Generated a {label} sourcing plan. Exact mock-checkout prices come from the local source database; supplier/search links are included for review and future real adapters.",
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
            "Checkout uses selected source-card prices, not planning estimates.",
            "Supplier search links help review real options, but exact prices must come from supplier/API data before real checkout.",
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
    problems: list[str] = []
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
            continue
        selected_index = int(item.get("selectedSourceIndex", -1))
        if selected_index < 0:
            problems.append(f"{name}: no source candidate selected.")
            continue
        candidates = item.get("sourceCandidates") or []
        if selected_index >= len(candidates):
            problems.append(f"{name}: selected source index is invalid.")
            continue
        selected = candidates[selected_index]
        if selected.get("verificationStatus") != "verified":
            problems.append(f"{name}: selected source is not verified.")
        if selected.get("priceConfidence") != "exact" or float(selected.get("unitPrice", 0) or 0) <= 0:
            problems.append(f"{name}: selected source has no exact price.")
        if selected.get("sourceType") != "local_source_database" and not selected.get("productUrlVerified"):
            problems.append(f"{name}: selected source link is not verified.")
    return not problems, problems
