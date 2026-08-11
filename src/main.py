"""
FlyRank Internship - Backend Track - W5 - A9
The polite scraper

Target: https://books.toscrape.com (a public sandbox built for scraping practice)
Scope: first 3 catalogue pages -> all book detail pages found from them (60 books)

Run:
    python src/main.py
"""

from urllib.parse import urljoin

import requests

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

BASE_URL = "https://books.toscrape.com/"
USER_AGENT = "FlyRankInternshipA9/1.0 (+https://github.com/FarzeenSajjad/scraper)"
TIMEOUT_SECONDS = 8

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


if __name__ == "__main__":
    check_robots()
