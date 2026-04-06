#!/usr/bin/env python3
"""
Scrape event details from superbooth.com for all events listed in index.html.
Outputs structured data to events_data.json.

Requirements: pip install requests beautifulsoup4
"""

import json
import re
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.superbooth.com/en/events/details/"

DAY_TO_DATE = {
    "Thursday May 7th": "2026-05-07",
    "Friday May 8th":   "2026-05-08",
    "Saturday May 9th": "2026-05-09",
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}


def extract_events_from_html(html_path: str) -> dict:
    """Parse the EVENTS JS object out of index.html."""
    text = Path(html_path).read_text(encoding="utf-8")
    match = re.search(r"const EVENTS\s*=\s*(\{.*?\});", text, re.DOTALL)
    if not match:
        raise ValueError("Could not find EVENTS object in index.html")
    return json.loads(match.group(1))


def scrape_event_page(url: str) -> dict:
    """
    Fetch a superbooth event detail page and extract time range + description.

    Page structure (confirmed):
      .location  → venue name
      .info      → full date/time string  e.g. "2026-05-07, 11:00 am–11:40 am"
      .ce_text   → artist bio / description paragraphs
    """
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"  ERROR fetching {url}: {e}")
        return {"time_range": None, "details": None, "error": str(e)}

    soup = BeautifulSoup(resp.text, "html.parser")

    # ── Time range (full string from the page) ──────────────────────────────
    time_range = None
    info_el = soup.find(class_="info")
    if info_el:
        time_range = info_el.get_text(" ", strip=True)

    # ── Artist bio / description ─────────────────────────────────────────────
    details = None
    text_el = soup.find(class_="ce_text")
    if text_el:
        # Preserve paragraph breaks
        for br in text_el.find_all("br"):
            br.replace_with("\n")
        paragraphs = [
            p.get_text(" ", strip=True)
            for p in text_el.find_all("p")
            if p.get_text(strip=True)
        ]
        if paragraphs:
            details = "\n\n".join(paragraphs)
        else:
            details = text_el.get_text("\n", strip=True)
        details = re.sub(r"\n{3,}", "\n\n", details).strip()

    return {"time_range": time_range, "details": details}


def main():
    html_path = Path(__file__).parent / "index.html"
    output_path = Path(__file__).parent / "events_data.json"

    print("Parsing events from index.html …")
    events_by_day = extract_events_from_html(str(html_path))

    results = []
    total = sum(len(v) for v in events_by_day.values())
    count = 0

    for day_label, events in events_by_day.items():
        date = DAY_TO_DATE.get(day_label, day_label)
        for ev in events:
            count += 1
            url = BASE_URL + ev["slug"]
            print(f"[{count}/{total}] {ev['title']}")

            scraped = scrape_event_page(url)

            # Prefer the scraped time range (includes end time);
            # fall back to the start time from index.html
            time_str = scraped.get("time_range") or ev["time"]

            record = {
                "event":    ev["title"],
                "place":    ev["venue"],
                "date":     date,
                "time":     time_str,
                "category": ev["category"],
                "url":      url,
                "details":  scraped.get("details"),
            }
            if scraped.get("error"):
                record["scrape_error"] = scraped["error"]

            results.append(record)

            # Be polite — 0.5 s between requests
            time.sleep(0.5)

    output_path.write_text(
        json.dumps(results, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    # Also write a JS file so the data loads without a local server
    js_path = Path(__file__).parent / "events_data.js"
    js_path.write_text(
        "window.EVENTS_DETAILS = " + json.dumps(results, ensure_ascii=False) + ";",
        encoding="utf-8"
    )
    print(f"\nDone. {len(results)} events saved to {output_path} and {js_path}")


if __name__ == "__main__":
    main()
