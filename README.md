# The polite scraper

A small, polite scraping pipeline for [Books to Scrape](https://books.toscrape.com), a public
sandbox built for practising web scraping. It downloads the first 3 catalogue pages, visits all
60 book pages it finds, turns the messy HTML into clean, schema-checked JSON, survives a broken
page without crashing, and writes an honest report at the end of every run.

## Target classification

- **Site:** `books.toscrape.com`, part of the `toscrape.com` sandbox network.
- **Why it's fair game:** the site's own homepage describes itself as "a fictional bookstore that
  desperately wants to be scraped... a safe place for beginners learning web scraping and for
  developers validating their scraping technologies." Every page also carries the banner
  *"Warning! This is a demo website for web scraping purposes."* That is explicit, on-page
  permission, and it's the only kind of site this project touches.
- **Scope:** the first 3 catalogue pages only (`catalogue/page-1.html` → `page-3.html`), plus the
  ~60 book detail pages linked from them. Nothing else on the site is requested.
- **robots.txt result:** `https://books.toscrape.com/robots.txt` returns a **404** — no robots
  file found. A missing file is not permission by itself; the on-page statement above is what
  makes this target appropriate.
- **What is collected:** title, price, availability, star rating, description, and the book's own
  URL — public catalogue data, nothing behind a login.

**I will not reuse this code on another site without checking its rules and terms first.**

## Lane

Python 3.10+ · `requests` (HTTP) · `BeautifulSoup` (HTML parsing) · `Pydantic` (schema validation)

## Run it

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python src/main.py
```

First run fetches everything from the network and populates `cache/`. Re-running reads from the
cache and finishes in a few seconds. Outputs land in `output/`:

- `output/books.json` — validated, deduplicated records (60 on a clean run)
- `output/errors.json` — any record that failed validation, with the reason
- `output/run-report.json` — counts and timing for the run

## Record schema

```json
{
  "title": "A Light in the Attic",
  "product_url": "https://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html",
  "price_text": "£51.77",
  "price_gbp": 51.77,
  "availability_text": "In stock (22 available)",
  "rating_text": "Three",
  "rating_value": 3,
  "description": "...",
  "source_page": "https://books.toscrape.com/catalogue/page-1.html",
  "fetched_at": "2026-08-13T05:38:45Z"
}
```

`product_url` is each record's canonical identity — re-running the scraper updates records, it
never duplicates them (idempotent).

## Politeness rules

- **User-agent:** every request identifies itself as `PoliteBookScraper/1.0 (+repo link)`.
- **Timeout:** every request gives up after 8 seconds rather than hanging forever.
- **Delay:** at least 500ms between real (non-cached) requests to the site.
- **Cache:** every page is saved to `cache/` on first fetch; re-runs during development read the
  cache and never hit the site again for the same URL.
- **Status checks:** only a `200` is treated as a page to parse. `5xx`/timeouts get one retry;
  `404` and `403` are never retried.

## Why no browser was needed

Every field this scraper collects — title, price, availability, rating, description — is already
present in the HTML the server sends back on the first request. There's no client-side JavaScript
building the page afterward, so rendering it in a real or headless browser would only add cost
(startup time, memory, complexity) for no extra data.

## A deliberately broken run

Setting `INJECT_BROKEN_URL = True` in `src/main.py` adds one made-up book URL to the list before
fetching. The run still finishes, `books.json` still has the 60 good records, and
`run-report.json` reports `"failed_pages": 1`. Verified locally: the fake URL returned a real
`404`, was correctly not retried, and the 60 good books were unaffected.

## Sample run report

A clean run against the live site:

```json
{
  "start_time": "2026-08-13T05:51:04Z",
  "duration_seconds": 171.38,
  "robots_check": "no robots file found (404)",
  "catalogue_pages_requested": 3,
  "book_urls_discovered": 60,
  "pages_fetched_from_network": 60,
  "cache_hits": 0,
  "valid_records": 60,
  "invalid_records": 0,
  "failed_pages": 0
}
```

## Proving it survives a broken page

Setting `INJECT_BROKEN_URL = True` in `src/main.py` adds one made-up book URL to the list before
fetching. Tested locally: the fake URL returned a real `404`, was correctly not retried (404s are
never retried — the page doesn't exist, asking again won't create it), the run still finished, and
`run-report.json` reported `"book_urls_discovered": 61, "valid_records": 60, "invalid_records": 1,
"failed_pages": 1"`. One bad page never took the other 60 down with it.