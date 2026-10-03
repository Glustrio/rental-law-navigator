"""Module A, step 2: merge duplicate candidates into the final rule set (out/rules.json).

Several documents describe the same law (a statute and a city page explaining it). For
each (jurisdiction, category) bucket with more than one candidate, Claude groups the
candidates that describe the same rule and picks the best-supported one; the canonical
record keeps its own verbatim quote, so no text is ever rewritten. Precedence links
between state and local rules are then filled in deterministically.
"""

import json
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

from navigator.extract import log_call
from navigator.llm import call_json, client
from navigator.paths import EXTRACTIONS, OUT, RULES_OUT, WORK

JURIS_CODE = {
    "CA": "CA", "NJ": "NJ", "MA": "MA",
    "Los Angeles, CA": "LA", "San Francisco, CA": "SF", "San Diego, CA": "SD", "Berkeley, CA": "BER",
    "Santa Ana, CA": "SA", "Jersey City, NJ": "JC", "Hoboken, NJ": "HOB", "Newark, NJ": "NWK",
    "Boston, MA": "BOS", "Cambridge, MA": "CAM",
}
CATEGORY_CODE = {
    "rent_increase_limits": "RENT", "just_cause_eviction": "EVICT", "security_deposits": "DEP",
    "application_screening_fees": "FEE", "screening_restrictions": "SCREEN", "algorithmic_rent_setting": "ALG",
}

GROUP_SCHEMA = {
    "type": "object",
    "properties": {
        "groups": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "member_indices": {"type": "array", "items": {"type": "integer"}},
                    "canonical_index": {"type": "integer"},
                    "effective_date": {"type": ["string", "null"]},
                    "conflict_type": {"type": "string", "enum": ["none", "preemption", "inconsistent_sources", "other"]},
                    "conflict_note": {"type": ["string", "null"]},
                    "reason": {"type": "string"},
                },
                "required": ["member_indices", "canonical_index", "effective_date", "conflict_type", "conflict_note", "reason"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["groups"],
    "additionalProperties": False,
}

GROUP_SYSTEM = """You deduplicate rental housing rule records extracted from different documents.

You get numbered candidate records that share one jurisdiction and one category. Group the
candidates that describe the same legal rule (the same law, ordinance or bill, even when the
citation is written differently). Candidates for genuinely different rules stay in separate groups.
Every candidate index must appear in exactly one group.

For each group:
- canonical_index: the candidate whose quote and citation best support the rule. Prefer official
  statute or ordinance text over agency summaries, and agency pages over news or law-firm pages.
- effective_date: the best-supported effective date (YYYY-MM-DD when known). If sources give
  different dates, keep the date in the official enacted text and set conflict_type to
  inconsistent_sources with a note naming both dates and their sources.
- conflict_type / conflict_note: carry forward any preemption or source conflict the members raise.
- reason: one sentence on why these belong together and why the canonical one was chosen.
"""


def load_candidates():
    candidates = []
    for path in sorted(EXTRACTIONS.glob("*.json")):
        candidates.extend(json.loads(path.read_text())["rules"])
    return candidates


def summarize(i, rule):
    return {
        "index": i,
        "title": rule["title"],
        "citation": rule["citation"],
        "status": rule["status"],
        "effective_date": rule["effective_date"],
        "requirement": rule["requirement"],
        "key_value": rule["key_value"],
        "source": f'{rule["source_doc_id"]} ({rule["source_type"]})',
        "quoted_span": rule["quoted_span"][:300],
        "conflict_type": rule["conflict_type"],
        "conflict_note": rule["conflict_note"],
    }


def group_bucket(llm, key, rules):
    if len(rules) == 1:
        r = rules[0]
        return [{"member_indices": [0], "canonical_index": 0, "effective_date": r["effective_date"],
                 "conflict_type": r["conflict_type"], "conflict_note": r["conflict_note"], "reason": "single candidate"}]
    prompt = (f"Jurisdiction: {key[0]}\nCategory: {key[1]}\n\nCandidates:\n"
              + json.dumps([summarize(i, r) for i, r in enumerate(rules)], indent=1))
    result, meta = call_json(llm, GROUP_SYSTEM, prompt, GROUP_SCHEMA, max_tokens=16000, effort="medium")
    log_call({"step": "consolidate", "bucket": list(key), "candidates": len(rules), **meta,
              "groups": result["groups"]})
    groups = [g for g in result["groups"] if g["member_indices"]]
    seen = {i for g in groups for i in g["member_indices"]}
    for i, r in enumerate(rules):  # anything the model left out becomes its own rule
        if i not in seen:
            groups.append({"member_indices": [i], "canonical_index": i, "effective_date": r["effective_date"],
                           "conflict_type": r["conflict_type"], "conflict_note": r["conflict_note"],
                           "reason": "not grouped by model"})
    for g in groups:
        if g["canonical_index"] not in g["member_indices"]:
            g["canonical_index"] = g["member_indices"][0]
    return groups


def build_rule(rule_id, canonical, members, group):
    rule = dict(canonical)
    rule["team_rule_id"] = rule_id
    rule["effective_date"] = group["effective_date"]
    rule["conflict_type"] = group["conflict_type"]
    rule["conflict_note"] = group["conflict_note"]
    rule["conflict_flag"] = group["conflict_type"] != "none"
    rule["also_supported_by"] = sorted({m["source_doc_id"] for m in members} - {canonical["source_doc_id"]})
    rule["merge_reason"] = group["reason"]
    return rule


def link_precedence(rules):
    """Fill overrides/interaction between state rules that yield and local rules that displace them."""
    by_state_cat = defaultdict(list)
    for r in rules:
        by_state_cat[(r["jurisdiction"][-2:], r["category"])].append(r)
    for r in rules:
        r["overrides"], r["interaction"] = [], None
        peers = by_state_cat[(r["jurisdiction"][-2:], r["category"])]
        if r["level"] == "state" and r["yields_to_local_rule"]:
            local = [p["team_rule_id"] for p in peers if p["level"] == "city" and p["displaces_state_rule"]]
            if local:
                r["overrides"] = local
                r["interaction"] = f"Yields to {', '.join(local)} where the local rule covers the unit."
        elif r["level"] == "city" and r["displaces_state_rule"]:
            state = [p["team_rule_id"] for p in peers if p["level"] == "state" and p["yields_to_local_rule"]]
            if state:
                r["overrides"] = state
                r["interaction"] = f"Supersedes {', '.join(state)} for units it covers."


def main():
    candidates = load_candidates()
    buckets = defaultdict(list)
    for c in candidates:
        buckets[(c["jurisdiction"], c["category"])].append(c)
    print(f"{len(candidates)} candidates in {len(buckets)} buckets", file=sys.stderr)

    llm = client()
    keys = sorted(buckets)
    with ThreadPoolExecutor(max_workers=6) as pool:
        grouped = dict(zip(keys, pool.map(lambda k: group_bucket(llm, k, buckets[k]), keys), strict=True))

    rules = []
    status_order = {"in_force": 0, "not_yet_effective": 1, "pending": 2, "failed": 3}
    for key in sorted(keys, key=lambda k: (len(k[0]) > 2, k[0], k[1])):
        bucket = buckets[key]
        groups = sorted(grouped[key], key=lambda g: (status_order[bucket[g["canonical_index"]]["status"]],
                                                      bucket[g["canonical_index"]]["citation"]))
        for n, g in enumerate(groups, 1):
            rule_id = f"{JURIS_CODE[key[0]]}-{CATEGORY_CODE[key[1]]}-{n:02d}"
            members = [bucket[i] for i in g["member_indices"]]
            rules.append(build_rule(rule_id, bucket[g["canonical_index"]], members, g))
    link_precedence(rules)

    OUT.mkdir(exist_ok=True)
    (WORK / "rules_full.json").write_text(json.dumps(rules, indent=1))
    RULES_OUT.write_text(json.dumps({"rules": [submission_record(r) for r in rules]}, indent=1))
    print(f"wrote {len(rules)} rules to {RULES_OUT}", file=sys.stderr)


SUBMISSION_FIELDS = ["team_rule_id", "jurisdiction", "level", "category", "status", "title", "requirement",
                     "key_value", "coverage_conditions", "exemptions", "overrides", "interaction", "effective_date",
                     "citation", "source_doc_id", "source_url", "quoted_span", "confidence", "conflict_flag",
                     "conflict_note"]


def submission_record(rule):
    record = {k: rule.get(k) for k in SUBMISSION_FIELDS}
    record["penalty"] = rule.get("penalty")
    record["retrieved_at"] = rule.get("retrieved_at")
    if rule.get("source_origin") == "supplement":
        record["source_note"] = "Secondary source fetched from the corpus link list; official text not in corpus."
    return record


if __name__ == "__main__":
    main()
