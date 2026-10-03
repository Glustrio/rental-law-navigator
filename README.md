# Rental Housing Law Navigator

For any apartment address in the sample, this answers: which housing rules apply here on a given date, and what is about to change? Every answer cites the source law and quotes it verbatim.

Built for the RealPage × Hack-Nation challenge (7th Global AI Hackathon, October 2026).

> **Not legal advice.** This is a research prototype. It summarizes public law text and can be wrong. Check the cited source and talk to a lawyer or local housing agency before acting.

**Live demo:** https://glustrio.github.io/rental-law-navigator/

## What it does

| Module | What happens | Code |
|---|---|---|
| A. Extract | Claude reads each corpus document and returns rule records in the challenge schema, plus machine-checkable coverage tests. Every quote is located in the source; rules whose quote can't be found are dropped. Duplicates across documents are merged. | `navigator/extract.py`, `navigator/consolidate.py` |
| B. Resolve and apply | Each address is geocoded with the Census Geocoder into its legal city (Van Nuys → Los Angeles, Dorchester → Boston). A deterministic engine tests every rule against year built and unit count and returns `applies`, `unknown`, `superseded`, `not_yet_effective` or `pending`, with the reason. | `navigator/geocode.py`, `navigator/engine.py` |
| C. Track change | Each change test is matched to our rules once, then the engine compares answers at the test's dates. | `navigator/changes.py` |
| Site | Address search, "as of" date picker, citations and quotes, conflict flags, all rules, change tests. The browser runs a port of the same engine; a test checks both agree on every address. | `site/` |

## Design choices

- **The model only reads; code decides.** Claude extracts rules and their coverage tests as data. Whether a rule reaches a building is decided by plain code that anyone can audit, so the same input always gives the same answer.
- **Unknown beats a guess.** Year built is only a year, so a building from a certificate-of-occupancy cutoff year (San Francisco 1979, Los Angeles 1978) is `unknown`. Rules that depend on owner type, which the data never has, are `unknown` unless the unit count already rules the exemption out.
- **Unit counts from use codes.** Where the assessor record has no unit count but its use code states a range (NJ class 4C is 5+ units, Cambridge 111 is 4–8 units, Boston A/112 is 7–30), the range is used and the explanation says so.
- **Verbatim citations.** Quotes are matched back to the source text and replaced with the document's own characters, so every `quoted_span` is exact.
- **Law vs. not law.** Pending bills are `pending` and never in force; failed proposals (the Massachusetts rent-control ballot question) are recorded as `failed` and never reported for an address.
- **Conflicts go to a human.** Possible preemption (New Jersey's FAIR Act and the Jersey City and Hoboken ordinances) is flagged only where both levels reach the address. Disagreeing published dates are flagged everywhere the rule applies.
- **Secondary sources are labeled.** The Jersey City and Hoboken algorithmic-pricing ordinances have no text in the starter corpus. We read the public news and law-firm pages from the corpus link list (one request each, no code-publisher sites), and every rule from them is marked as a secondary source with lower confidence.

## Run it

Requires Python 3.12+ and either an `ANTHROPIC_API_KEY` in `.env` or a logged-in [Claude Code](https://claude.com/claude-code) CLI. Node is only needed for the parity test.

```bash
make setup      # virtualenv + dependencies
make starter    # download the organizers' starter pack into starter/
make all        # geocode, fetch secondary sources, extract, consolidate, write outputs
make test       # unit tests and the Python/JavaScript parity test
make serve      # site at http://localhost:8000
```

Extraction results are cached per document in `work/extractions/`, so `make all` only calls the model for new documents. To process a document released mid-event, put its text in `extra_docs/` (and any new tests as `extra_docs/*tests*.json`) and run `make extract consolidate outputs`.

## Outputs

- `out/rules.json`: rule records in the challenge schema, each with citation, source URL, retrieval date and quoted span.
- `out/lookups.json`: results for all 500 sample addresses as of 2026-10-01.
- `out/changes.json`: affected and conflict-flagged addresses for each change test, with before/after results.
- `work/audit_log.jsonl`: every model call, with the document hash, model, token counts and outcome.

## Limits

- Coverage is only as good as the corpus. Where official ordinance text is missing (Hoboken, Jersey City, Newark), rules come from secondary sources or are absent.
- Year built stands in for certificate-of-occupancy dates, and owner type is never known.
- Not reviewed by a lawyer.
