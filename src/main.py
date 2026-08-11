"""
FlyRank Internship - Backend Track - W5 - A9
The polite scraper

Target: https://books.toscrape.com (a public sandbox built for scraping practice)
Scope: first 3 catalogue pages -> all book detail pages found from them (60 books)

Run:
    python src/main.py
"""

import re
import time
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin

import requests

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

BASE_URL = "https://books.toscrape.com/"
USER_AGENT = "FlyRankInternshipA9/1.0 (+https://github.com/FarzeenSajjad/scraper)"
TIMEOUT_SECONDS = 8
DELAY_SECONDS = 0.6  # >= 500ms between real (non-cached) requests

ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = ROOT / "cache"

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": USER_AGENT})


# ---------------------------------------------------------------------------
# Stage 0 - classify the target (robots.txt check, run once, printed)
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
# Stage 1 - fetch once, cache once
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


if __name__ == "__main__":
    check_robots()
    fetch(urljoin(BASE_URL, "catalogue/page-1.html"))
