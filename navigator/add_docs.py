"""Add documents for a new or existing jurisdiction to extra_docs/.

    python -m navigator.add_docs --jurisdiction "Santa Monica, CA" --type official URL [URL ...]
    python -m navigator.add_docs --jurisdiction "Cambridge, MA" --file ordinance.txt

Each document is saved as plain text with a provenance header (source, retrieval time,
jurisdiction, source type). `make extract consolidate outputs` then processes only the new
files; nothing else in the pipeline needs to change.
"""

import argparse
import io
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

import requests
from pypdf import PdfReader

from navigator.paths import EXTRA_DOCS
from navigator.supplement import HEADERS, page_text


def fetch_text(url):
    resp = requests.get(url, headers=HEADERS, timeout=60)
    resp.raise_for_status()
    if url.lower().endswith(".pdf") or resp.headers.get("content-type", "").startswith("application/pdf"):
        reader = PdfReader(io.BytesIO(resp.content))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    return page_text(resp.text)


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60]


def save(text, source, jurisdiction, source_type, name):
    EXTRA_DOCS.mkdir(exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    header = (f"SOURCE: {source}\nRETRIEVED: {stamp}\nJURISDICTION: {jurisdiction}\n"
              f"SOURCE TYPE: {source_type}\n\n")
    path = EXTRA_DOCS / f"{name}.txt"
    path.write_text(header + text)
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--jurisdiction", required=True, help="'ST' or 'City, ST'")
    parser.add_argument("--type", default="official", help="official, or e.g. 'secondary (news)'")
    parser.add_argument("--file", type=Path, help="a local text file instead of URLs")
    parser.add_argument("urls", nargs="*")
    args = parser.parse_args()

    prefix = "X-" + slug(args.jurisdiction)
    if args.file:
        path = save(args.file.read_text(), args.file.name, args.jurisdiction, args.type, f"{prefix}-{slug(args.file.stem)}")
        print(f"saved {path}", file=sys.stderr)
    for url in args.urls:
        text = fetch_text(url)
        name = f"{prefix}-{slug(Path(url.split('?')[0]).stem)}"
        print(f"saved {save(text, url, args.jurisdiction, args.type, name)} ({len(text)} chars)", file=sys.stderr)


if __name__ == "__main__":
    main()
