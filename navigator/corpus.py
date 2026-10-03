"""Load corpus documents and locate quoted spans in them."""

import csv
import hashlib
import re
from dataclasses import dataclass

from rapidfuzz import fuzz

from navigator.paths import CORPUS_DIR, EXTRA_DOCS, MANIFEST, WORK

SUPPLEMENT_DIR = WORK / "supplement"

_QUOTE_FIXES = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"', "–": "-",
                              "—": "-", " ": " ", "﻿": " "})


@dataclass
class Document:
    doc_id: str
    jurisdictions: str
    url: str
    source_type: str
    retrieved_at: str
    origin: str  # "corpus", "supplement" or "extra"
    text: str

    @property
    def is_official(self):
        return self.source_type.startswith("official")

    @property
    def sha256(self):
        return hashlib.sha256(self.text.encode()).hexdigest()


def _retrieved_from_header(text):
    m = re.search(r"RETRIEVED:\s*([^\n]+)", text[:600])
    return m.group(1).strip() if m else ""


def load_documents(include_supplement=True):
    docs = []
    with open(MANIFEST) as f:
        manifest = {r["doc_id"]: r for r in csv.DictReader(f)}
    for doc_id, row in manifest.items():
        path = CORPUS_DIR / f"{doc_id}.txt"
        if path.exists():
            text = path.read_text()
            docs.append(Document(doc_id, row["jurisdictions"], row["url"], row["source_type"],
                                 row["retrieved_at"] or _retrieved_from_header(text), "corpus", text))
        elif include_supplement and (SUPPLEMENT_DIR / f"{doc_id}.txt").exists():
            text = (SUPPLEMENT_DIR / f"{doc_id}.txt").read_text()
            docs.append(Document(doc_id, row["jurisdictions"], row["url"], row["source_type"],
                                 _retrieved_from_header(text), "supplement", text))
    for path in sorted(EXTRA_DOCS.glob("*.txt")) if EXTRA_DOCS.exists() else []:
        text = path.read_text()
        url = re.search(r"SOURCE:\s*(\S+)", text[:600])
        juris = re.search(r"JURISDICTION:\s*([^\n]+)", text[:600])
        stype = re.search(r"SOURCE TYPE:\s*([^\n]+)", text[:600])
        docs.append(Document(path.stem, juris.group(1).strip() if juris else "", url.group(1) if url else "",
                             stype.group(1).strip() if stype else "official", _retrieved_from_header(text),
                             "extra", text))
    # Two link-only rows point at the same law-firm article; keep the first copy.
    seen, unique = set(), []
    for d in docs:
        if d.sha256 not in seen:
            seen.add(d.sha256)
            unique.append(d)
    return unique


def _normalize_with_map(text):
    """Collapse whitespace and unify quote characters, keeping a map back to the original offsets."""
    out, index = [], []
    prev_space = False
    # Every entry in _QUOTE_FIXES maps one character to one character, so offsets line up.
    for i, ch in enumerate(text.translate(_QUOTE_FIXES)):
        if ch.isspace():
            if prev_space:
                continue
            out.append(" ")
            prev_space = True
        else:
            out.append(ch)
            prev_space = False
        index.append(i)
    return "".join(out), index


def _normalize(s):
    return re.sub(r"\s+", " ", s.translate(_QUOTE_FIXES)).strip()


def locate_span(doc_text, quote, min_score=90):
    """Return (exact_text_from_document, score) for the best match of quote, or (None, score).

    Models occasionally change whitespace or a curly quote while copying. We find where
    the quote really sits in the source and return the document's own characters, so
    every quoted_span we publish is verbatim source text.
    """
    norm_doc, index = _normalize_with_map(doc_text)
    norm_quote = _normalize(quote)
    if not norm_quote:
        return None, 0
    pos = norm_doc.find(norm_quote)
    if pos >= 0:
        start, end = index[pos], index[pos + len(norm_quote) - 1] + 1
        return doc_text[start:end], 100
    align = fuzz.partial_ratio_alignment(norm_quote, norm_doc, score_cutoff=min_score)
    if align is None:
        return None, fuzz.partial_ratio(norm_quote, norm_doc)
    start, end = index[align.dest_start], index[max(align.dest_start, align.dest_end - 1)] + 1
    return doc_text[start:end], align.score
