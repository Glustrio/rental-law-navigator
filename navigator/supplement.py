"""Fetch the link-only secondary sources (news and law-firm pages) once, as plain text.

The starter corpus has no text for some rules the tests depend on (the Jersey City
and Hoboken algorithmic-pricing bans, for example). Their official code pages live on
code publishers whose terms are still under review, so we leave those alone and
only read the public secondary pages listed in links_only.csv, one request each.
Every saved file records its URL, retrieval time and that it is a secondary source.
"""

import csv
import re
import sys
from datetime import UTC, datetime

import requests
from bs4 import BeautifulSoup

from navigator.paths import STARTER, WORK

LINKS_ONLY = STARTER / "corpus" / "links_only.csv"
SUPPLEMENT_DIR = WORK / "supplement"
SKIP_SOURCE_TYPES = {"code publisher"}  # terms under review; organizers say don't scrape
SKIP_HOSTS = ("mass.gov",)  # official page that blocks automated capture
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 "
           "(KHTML, like Gecko) Chrome/126 Safari/537.36"}


def page_text(html):
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "header", "footer", "aside", "form", "noscript", "svg"]):
        tag.decompose()
    main = soup.find("article") or soup.find("main") or soup.body or soup
    text = main.get_text("\n")
    lines = [re.sub(r"\s+", " ", ln).strip() for ln in text.splitlines()]
    return "\n".join(ln for ln in lines if ln)


def main():
    SUPPLEMENT_DIR.mkdir(parents=True, exist_ok=True)
    with open(LINKS_ONLY) as f:
        rows = list(csv.DictReader(f))
    for row in rows:
        url = row["url"]
        if row["source_type"] in SKIP_SOURCE_TYPES or any(h in url for h in SKIP_HOSTS):
            continue
        try:
            resp = requests.get(url, headers=HEADERS, timeout=30)
        except requests.RequestException as exc:
            print(f"{row['doc_id']}: {type(exc).__name__}", file=sys.stderr)
            continue
        if resp.status_code != 200:
            print(f"{row['doc_id']}: HTTP {resp.status_code}, skipped", file=sys.stderr)
            continue
        text = page_text(resp.text)
        stamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
        header = f"SOURCE: {url}\nRETRIEVED: {stamp}\nSOURCE TYPE: {row['source_type']} (fetched by our pipeline; not in the starter corpus)\n\n"
        (SUPPLEMENT_DIR / f"{row['doc_id']}.txt").write_text(header + text)
        print(f"{row['doc_id']}: {len(text)} chars", file=sys.stderr)


if __name__ == "__main__":
    main()
