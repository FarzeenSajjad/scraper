"""
The polite scraper

Target: https://books.toscrape.com (a public sandbox built for scraping practice)
Scope: first 3 catalogue pages -> all book detail pages found from them (60 books)

Run:
    python src/main.py
"""

import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

BASE_URL = "https://books.toscrape.com/"
CATALOGUE_START = urljoin(BASE_URL, "catalogue/page-1.html")
MAX_CATALOGUE_PAGES = 3

USER_AGENT = "PoliteBookScraper/1.0 (+https://github.com/FarzeenSajjad/scraper)"
TIMEOUT_SECONDS = 8
DELAY_SECONDS = 0.6  # >= 500ms between real (non-cached) requests

ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = ROOT / "cache"

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": USER_AGENT})


# ---------------------------------------------------------------------------
# Robots check
# ---------------------------------------------------------------------------

def check_robots() -> str:
    """Fetch robots.txt once and return a short human-readable summary."""
    robots_url = urljoin(BASE_URL, "robots.txt")
    try:
        resp = SESSION.get(robots_url, timeout=TIMEOUT_SECONDS)
        if resp.status_code == 200 and resp.text.strip():
            summary = f"robots.txt found (status {resp.status_code}), {len(resp.text.splitlines())} lines"
        elif resp.status_code == 404:
            summary = "no robots file found (404)"
        else:
            summary = f"robots.txt request returned status {resp.status_code}"
    except requests.RequestException as exc:
        summary = f"could not fetch robots.txt: {exc}"
    print(f"[STAGE 0] {summary}")
    return summary


# ---------------------------------------------------------------------------
# Fetch + cache
# ---------------------------------------------------------------------------

def cache_path_for(url: str) -> Path:
    """Turn a URL into a safe, deterministic cache filename."""
    safe_name = re.sub(r"[^a-zA-Z0-9]+", "-", url).strip("-")
    return CACHE_DIR / f"{safe_name}.html"


def fetch(url: str, retry_on_failure: bool = True) -> tuple[Optional[str], dict]:
    """
    Fetch a URL politely, using the cache when available.

    Returns (html_or_None, meta) where meta has keys:
        source: "cache" | "network" | "failed"
        status_code: int or None
        size: bytes of content
    """
    path = cache_path_for(url)

    if path.exists():
        html = path.read_text(encoding="utf-8")
        print(f"CACHE HIT {url} ({len(html)} bytes)")
        return html, {"source": "cache", "status_code": 200, "size": len(html)}

    attempts = 2 if retry_on_failure else 1
    last_status = None
    for attempt in range(1, attempts + 1):
        try:
            resp = SESSION.get(url, timeout=TIMEOUT_SECONDS)
            resp.encoding = "utf-8"  # site serves UTF-8; avoid requests mis-guessing and mangling £ etc.
            last_status = resp.status_code
        except requests.RequestException as exc:
            print(f"FETCH FAILED {url} (attempt {attempt}): {exc}")
            if attempt < attempts:
                time.sleep(1 * attempt)
                continue
            return None, {"source": "failed", "status_code": None, "size": 0}

        if resp.status_code == 200:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            path.write_text(resp.text, encoding="utf-8")
            print(f"FETCH {url} -> 200 ({len(resp.text)} bytes)")
            time.sleep(DELAY_SECONDS)
            return resp.text, {"source": "network", "status_code": 200, "size": len(resp.text)}

        if 500 <= resp.status_code < 600 and attempt < attempts:
            print(f"FETCH {url} -> {resp.status_code}, retrying once")
            time.sleep(1 * attempt)
            continue

        print(f"FETCH {url} -> {resp.status_code} (not retried)")
        time.sleep(DELAY_SECONDS)
        return None, {"source": "failed", "status_code": resp.status_code, "size": 0}

    return None, {"source": "failed", "status_code": last_status, "size": 0}


# ---------------------------------------------------------------------------
# Discover catalogue pages
# ---------------------------------------------------------------------------

def discover_book_urls() -> list[tuple[str, str]]:
    """Returns a de-duplicated list of (book_url, source_catalogue_page) pairs."""
    pairs: list[tuple[str, str]] = []
    page_url = CATALOGUE_START
    pages_seen = 0

    while page_url and pages_seen < MAX_CATALOGUE_PAGES:
        html, meta = fetch(page_url)
        pages_seen += 1
        if html is None:
            print(f"[STAGE 2] could not load catalogue page {page_url}, stopping discovery")
            break

        soup = BeautifulSoup(html, "html.parser")

        for anchor in soup.select("article.product_pod h3 a"):
            href = anchor.get("href")
            if href:
                pairs.append((urljoin(page_url, href), page_url))

        next_link = soup.select_one("li.next a")
        page_url = urljoin(page_url, next_link["href"]) if next_link else None

    seen: dict[str, str] = {}
    for url, source in pairs:
        seen.setdefault(url, source)  # de-dupe, keep first source page

    print(f"[STAGE 2] catalogue_pages={pages_seen} discovered={len(pairs)} unique_urls={len(seen)}")
    return list(seen.items())


# ---------------------------------------------------------------------------
# Extract raw record
# ---------------------------------------------------------------------------

def extract_raw_record(url: str, html: str, source_page: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    product = soup.select_one("div.product_main")

    title = product.select_one("h1").get_text(strip=True) if product else None

    price_text = None
    price_el = soup.select_one("p.price_color")
    if price_el:
        price_text = price_el.get_text(strip=True)

    availability_text = None
    avail_el = soup.select_one("p.availability")
    if avail_el:
        availability_text = avail_el.get_text(strip=True)

    rating_text = None
    rating_el = soup.select_one("p.star-rating")
    if rating_el:
        classes = rating_el.get("class", [])
        rating_text = next((c for c in classes if c != "star-rating"), None)

    description = None
    desc_heading = soup.find("div", id="product_description")
    if desc_heading:
        desc_p = desc_heading.find_next_sibling("p")
        if desc_p:
            description = desc_p.get_text(strip=True)

    return {
        "title": title,
        "product_url": url,
        "price_text": price_text,
        "availability_text": availability_text,
        "rating_text": rating_text,
        "description": description,
        "source_page": source_page,
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
    }


if __name__ == "__main__":
    check_robots()
    urls = discover_book_urls()
    first_url, first_source = urls[0]
    html, meta = fetch(first_url)
    record = extract_raw_record(first_url, html, first_source)
    print(json.dumps(record, indent=2, ensure_ascii=False))
    print("[STAGE 3] detail_pages=1 (demo run - fetches all 60 in Stage 5)")
