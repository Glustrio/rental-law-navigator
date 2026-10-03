"""Module A, step 1: read every document and extract candidate rule records with Claude.

One model call per document. The model returns rules in a fixed JSON shape, including a
machine-checkable coverage block that the lookup engine evaluates later. Every quoted
span is then located in the source text; a rule whose quote can't be found is dropped.

Raw candidates go to work/extractions/<doc_id>.json; every call is logged to
work/audit_log.jsonl.
"""

import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

import anthropic

from navigator.corpus import load_documents, locate_span
from navigator.llm import call_json
from navigator.paths import AUDIT_LOG, DEFAULT_AS_OF, EXTRACTIONS

CATEGORIES = [
    "rent_increase_limits",
    "just_cause_eviction",
    "security_deposits",
    "application_screening_fees",
    "screening_restrictions",
    "algorithmic_rent_setting",
]
JURISDICTIONS = [
    "CA", "NJ", "MA",
    "Los Angeles, CA", "San Francisco, CA", "San Diego, CA", "Berkeley, CA", "Santa Ana, CA",
    "Jersey City, NJ", "Hoboken, NJ", "Newark, NJ",
    "Boston, MA", "Cambridge, MA",
]

NULLABLE_STRING = {"type": ["string", "null"]}
NULLABLE_INT = {"type": ["integer", "null"]}

COVERAGE_SCHEMA = {
    "type": "object",
    "properties": {
        "min_units": {**NULLABLE_INT, "description": "Building must have at least this many units to be covered."},
        "max_units": {**NULLABLE_INT, "description": "Building must have at most this many units to be covered."},
        "built_on_or_before": {**NULLABLE_STRING, "description": "YYYY-MM-DD. Covered only if first built / certificate of occupancy on or before this date."},
        "built_after": {**NULLABLE_STRING, "description": "YYYY-MM-DD. Covered only if built after this date."},
        "min_building_age_years": {**NULLABLE_INT, "description": "Rolling age test, e.g. 15 for 'certificate of occupancy issued more than 15 years ago'."},
        "unresolvable_conditions": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Conditions that decide coverage for an ordinary multifamily rental building but cannot be known from an assessor record (year built, unit count, use code). Example: 'owner is a natural person who owns no more than two properties' when that decides whether the rule applies. Leave empty when the rule covers ordinary rentals regardless.",
        },
    },
    "required": ["min_units", "max_units", "built_on_or_before", "built_after", "min_building_age_years", "unresolvable_conditions"],
    "additionalProperties": False,
}

EXEMPTION_SCHEMA = {
    "type": "object",
    "properties": {
        "description": {"type": "string"},
        "if_units_at_most": {**NULLABLE_INT, "description": "Exemption can only apply when the building has at most this many units."},
        "if_built_after": {**NULLABLE_STRING, "description": "YYYY-MM-DD. Exemption applies to buildings built after this date."},
        "if_younger_than_years": {**NULLABLE_INT, "description": "Exemption applies to buildings younger than this many years (rolling)."},
        "needs_unknown_fact": {"type": "boolean", "description": "True only when, after the unit and year tests above, whether the exemption applies still depends on a fact an assessor record lacks (owner type, owner occupancy, subsidy contract)."},
    },
    "required": ["description", "if_units_at_most", "if_built_after", "if_younger_than_years", "needs_unknown_fact"],
    "additionalProperties": False,
}

RULE_SCHEMA = {
    "type": "object",
    "properties": {
        "jurisdiction": {"type": "string", "enum": JURISDICTIONS},
        "level": {"type": "string", "enum": ["state", "city"]},
        "category": {"type": "string", "enum": CATEGORIES},
        "status": {"type": "string", "enum": ["in_force", "not_yet_effective", "pending", "failed"]},
        "title": {"type": "string"},
        "requirement": {"type": "string", "description": "One or two plain-language sentences a renter could act on."},
        "key_value": NULLABLE_STRING,
        "coverage_conditions": {"type": "string", "description": "Who and what is covered, in words."},
        "exemptions": NULLABLE_STRING,
        "effective_date": {**NULLABLE_STRING, "description": "YYYY-MM-DD, YYYY-MM or YYYY. Date the rule takes or took effect."},
        "citation": {"type": "string", "description": "Official cite, e.g. 'Cal. Civ. Code § 1947.12', 'S.F. Admin. Code § 37.10C', 'M.G.L. c. 186, § 15B'."},
        "quoted_span": {"type": "string", "description": "Exact sentence(s) copied character for character from the document that support the rule. 20 to 400 characters."},
        "penalty": NULLABLE_STRING,
        "coverage": COVERAGE_SCHEMA,
        "exemption_tests": {"type": "array", "items": EXEMPTION_SCHEMA},
        "yields_to_local_rule": {"type": "boolean", "description": "True for a state rule that does not apply where a stricter local rule in the same category covers the unit (e.g. California's statewide rent cap yields to local rent control)."},
        "displaces_state_rule": {"type": "boolean", "description": "True for a local rule that governs instead of the state rule in the same category where it covers the unit."},
        "conflict_type": {"type": "string", "enum": ["none", "preemption", "inconsistent_sources", "other"],
                          "description": "preemption: this rule may override or be overridden by a rule at another level. inconsistent_sources: published sources disagree (e.g. two effective dates)."},
        "conflict_note": {**NULLABLE_STRING, "description": "Explain the conflict for human review; null when conflict_type is none."},
        "confidence": {"type": "number", "description": "0 to 1."},
    },
    "required": ["jurisdiction", "level", "category", "status", "title", "requirement", "key_value",
                 "coverage_conditions", "exemptions", "effective_date", "citation", "quoted_span", "penalty",
                 "coverage", "exemption_tests", "yields_to_local_rule", "displaces_state_rule",
                 "conflict_type", "conflict_note", "confidence"],
    "additionalProperties": False,
}

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "rules": {"type": "array", "items": RULE_SCHEMA},
        "notes": {"type": "string", "description": "Anything a reviewer should know: rules mentioned but not extractable, ambiguities."},
    },
    "required": ["rules", "notes"],
    "additionalProperties": False,
}

SYSTEM = f"""You extract rental housing rules from legal and government documents into structured records.

Scope: residential rental housing in these jurisdictions only: {", ".join(JURISDICTIONS)}.
Ignore rules from any other place, even if the document mentions them.

Extract rules in exactly these six categories:
- rent_increase_limits: caps or formulas limiting rent increases (rent control, rent stabilization, statewide caps). Also a state law that forbids local rent control.
- just_cause_eviction: limits on the reasons a landlord may end a tenancy, with notice and relocation rules.
- security_deposits: maximum deposit amounts, deposit interest, return rules.
- application_screening_fees: caps on application or screening fees, and limits on what may be charged up front (including broker fees charged to tenants).
- screening_restrictions: limits on using criminal history, source of income, or similar in tenant selection.
- algorithmic_rent_setting: bans or limits on software or algorithms that set rents or coordinate pricing.
Leave out everything else (habitability, notice-to-quit procedure, lead paint, discrimination rules outside tenant screening).

Status is as of {DEFAULT_AS_OF}:
- in_force: enacted and effective on or before {DEFAULT_AS_OF}.
- not_yet_effective: enacted, effective date after {DEFAULT_AS_OF}.
- pending: a bill, petition or proposal not yet enacted and still alive.
- failed: a proposal that was struck down, withdrawn, or died at the end of its legislative session. Record these too, so nobody reports them as law.

Rules for each record:
- One record per distinct rule. Several sections of one law that set one requirement are one rule.
  A document that only restates another jurisdiction's law (a city page explaining state deposit law) still yields that rule, with the jurisdiction of the law itself.
- quoted_span must be copied exactly from the document text, character for character, 20 to 400 characters, and must support the rule.
  Never paraphrase inside quoted_span. If no sentence in this document supports the rule, do not output the rule.
- citation is the official legal citation of the rule (statute section, municipal code section, bill number), not the URL.
- Never invent a rule, date or citation the document does not support. Prefer leaving a field null.
- coverage: fill the numeric and date tests only when the law states them. A certificate of occupancy cutoff goes in built_on_or_before.
  unresolvable_conditions is for coverage conditions an assessor record cannot answer and that matter for ordinary multifamily rentals; keep it empty otherwise.
- exemption_tests: list the exemptions that could matter for apartment buildings, with their unit or age limits.
  Skip exemptions for categories that are never ordinary apartments (hotels, hospitals, dormitories, nonprofit care facilities).
- yields_to_local_rule / displaces_state_rule capture precedence between state and local rules in the same category.
- conflict_note: flag preemption risks (a state law that may override a local ordinance), two different published effective dates, or other disagreements.
- confidence: lower it for secondary sources (news, law firms) and for rules whose details are partly missing.
"""


def build_prompt(doc):
    origin = {
        "corpus": "starter corpus",
        "supplement": "secondary page fetched from the corpus link list (not official text)",
        "extra": "document released during the event",
    }[doc.origin]
    return (
        f"Document {doc.doc_id}\n"
        f"Listed jurisdictions: {doc.jurisdictions}\n"
        f"Source type: {doc.source_type} ({origin})\n"
        f"URL: {doc.url}\n"
        f"Retrieved: {doc.retrieved_at}\n\n"
        f"<document>\n{doc.text}\n</document>\n\n"
        "Extract every rule in scope from this document."
    )


def log_call(entry):
    AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(AUDIT_LOG, "a") as f:
        f.write(json.dumps(entry) + "\n")


def extract_document(client, doc):
    started = time.time()
    result, meta = call_json(client, SYSTEM, build_prompt(doc), OUTPUT_SCHEMA, max_tokens=48000)
    kept, dropped = [], []
    for rule in result["rules"]:
        span, score = locate_span(doc.text, rule["quoted_span"])
        if span is None or len(span) < 20:
            dropped.append({"rule": rule, "reason": f"quoted_span not found in document (best match {score:.0f})"})
            continue
        rule["quoted_span"] = span
        rule["span_match_score"] = round(score, 1)
        rule["source_doc_id"] = doc.doc_id
        rule["source_url"] = doc.url
        rule["source_type"] = doc.source_type
        rule["source_origin"] = doc.origin
        rule["retrieved_at"] = doc.retrieved_at
        kept.append(rule)
    record = {
        "doc_id": doc.doc_id,
        "doc_sha256": doc.sha256,
        "model": meta["model"],
        "extracted_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "rules": kept,
        "dropped": dropped,
        "notes": result["notes"],
    }
    EXTRACTIONS.mkdir(parents=True, exist_ok=True)
    (EXTRACTIONS / f"{doc.doc_id}.json").write_text(json.dumps(record, indent=1))
    log_call({"step": "extract", "doc_id": doc.doc_id, "doc_sha256": doc.sha256, **meta,
              "rules_kept": len(kept), "rules_dropped": len(dropped), "seconds": round(time.time() - started, 1)})
    return doc.doc_id, len(kept), len(dropped)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--docs", nargs="*", help="only these doc_ids")
    parser.add_argument("--force", action="store_true", help="re-extract documents already done")
    parser.add_argument("--workers", type=int, default=6)
    args = parser.parse_args()

    docs = load_documents()
    if args.docs:
        docs = [d for d in docs if d.doc_id in args.docs]
    if not args.force:
        docs = [d for d in docs if not (EXTRACTIONS / f"{d.doc_id}.json").exists()]
    print(f"extracting {len(docs)} documents", file=sys.stderr)

    client = anthropic.Anthropic()
    failures = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(extract_document, client, d): d.doc_id for d in docs}
        for fut, doc_id in futures.items():
            try:
                _, kept, dropped = fut.result()
                print(f"{doc_id}: {kept} rules ({dropped} dropped)", file=sys.stderr)
            except Exception as exc:  # keep going; report at the end
                failures.append(doc_id)
                print(f"{doc_id}: FAILED {type(exc).__name__}: {exc}", file=sys.stderr)
    if failures:
        print(f"failed: {' '.join(failures)} (rerun to retry)", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
