"""Module A, step 2: merge candidates into the final rule set (out/rules.json).

Documents overlap: a statute and three city pages may all describe one law, and a long
page can yield several partial records for it. For each (jurisdiction, category) bucket,
Claude groups the candidates that come from the same law and writes one clean record per
law, choosing which candidate's verbatim quote and source to cite. Quotes are never
rewritten: the quote, source URL and retrieval date always come from a real candidate.
Precedence links between state and local rules are then filled in deterministically.
"""

import argparse
import hashlib
import json
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

from navigator.extract import COVERAGE_GUIDE, COVERAGE_SCHEMA, EXEMPTION_SCHEMA, log_call
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
NULLABLE_STRING = {"type": ["string", "null"]}

MERGED_RULE_SCHEMA = {
    "type": "object",
    "properties": {
        "member_indices": {"type": "array", "items": {"type": "integer"}},
        "quote_index": {"type": "integer", "description": "Candidate whose quoted_span and source to cite."},
        "status": {"type": "string", "enum": ["in_force", "not_yet_effective", "pending", "failed"]},
        "title": {"type": "string"},
        "requirement": {"type": "string"},
        "key_value": NULLABLE_STRING,
        "coverage_conditions": {"type": "string"},
        "exemptions": NULLABLE_STRING,
        "effective_date": NULLABLE_STRING,
        "citation": {"type": "string"},
        "penalty": NULLABLE_STRING,
        "coverage": COVERAGE_SCHEMA,
        "exemption_tests": {"type": "array", "items": EXEMPTION_SCHEMA},
        "yields_to_local_rule": {"type": "boolean"},
        "displaces_state_rule": {"type": "boolean"},
        "conflict_type": {"type": "string", "enum": ["none", "preemption", "inconsistent_sources", "other"]},
        "conflict_note": NULLABLE_STRING,
        "confidence": {"type": "number"},
        "reason": {"type": "string"},
    },
    "required": ["member_indices", "quote_index", "status", "title", "requirement", "key_value",
                 "coverage_conditions", "exemptions", "effective_date", "citation", "penalty", "coverage",
                 "exemption_tests", "yields_to_local_rule", "displaces_state_rule", "conflict_type",
                 "conflict_note", "confidence", "reason"],
    "additionalProperties": False,
}

MERGE_SCHEMA = {
    "type": "object",
    "properties": {"rules": {"type": "array", "items": MERGED_RULE_SCHEMA}},
    "required": ["rules"],
    "additionalProperties": False,
}

MERGE_SYSTEM = f"""You consolidate rental housing rule records extracted from different documents.

You get numbered candidate records that share one jurisdiction and one category. Several
candidates often describe the same law (the statute, an agency page explaining it, a news story),
or one long page produced several partial records for one law.

Produce one record per law: all candidates from the same statute, ordinance or code chapter in
this category merge into one record, even when they describe different provisions of it. Keep
separate records only for genuinely different laws, and for each bill or ballot question
(pending or failed proposals are never merged into enacted law). Every candidate index must
appear in exactly one record's member_indices. Drop nothing: a candidate that is out of place
still goes into the closest record.

For each record:
- quote_index: the member whose quoted_span best supports the headline requirement. Prefer official
  statute or ordinance text, then official agency pages, then news or law-firm pages.
- title, requirement (one or two plain sentences a renter could act on), key_value, coverage_conditions,
  exemptions, penalty: write them from what the members say. Do not add facts no member states.
- citation: the clean official cite, e.g. "Cal. Civ. Code § 1950.5", "S.F. Admin. Code ch. 37",
  "Berkeley Mun. Code ch. 13.76", "M.G.L. c. 186, § 15B", "N.J.S.A. 46:8-21.2", "Mass. S.2983 (194th Gen. Court)".
- status and effective_date: effective_date is when the rule's headline requirement first took effect
  (YYYY-MM-DD when known). For a long-standing law that was later amended, use the date the headline
  requirement started, not the amendment's operative date, and never an annual adjustment date (a yearly
  allowable-increase percentage starting March 1 is not the ordinance's effective date). If only a
  secondary source gives a date, use it and lower confidence. Set conflict_type to inconsistent_sources
  only when sources give different dates or values for the same thing (two published effective dates for
  one ordinance); an original date versus a later amendment date is not a conflict.
- confidence: 0 to 1; lower when the only support is a secondary source.
- Context: you also get short summaries of this jurisdiction's records in other categories. Use them only
  to fill coverage facts the members leave out (a rent ordinance's certificate-of-occupancy cutoff stated
  on the city's just-cause page, for example), and mention that source in coverage_conditions.
- reason: one sentence on what was merged and why.

Coverage, exemptions and precedence must follow these rules exactly; fix any member that breaks them:
{COVERAGE_GUIDE}
"""


def load_candidates():
    candidates = []
    for path in sorted(EXTRACTIONS.glob("*.json")):
        candidates.extend(json.loads(path.read_text())["rules"])
    return candidates


def summarize(i, rule):
    keep = ["title", "citation", "status", "effective_date", "requirement", "key_value", "coverage_conditions",
            "exemptions", "penalty", "coverage", "exemption_tests", "yields_to_local_rule", "displaces_state_rule",
            "conflict_type", "conflict_note", "confidence"]
    return {"index": i, "source": f'{rule["source_doc_id"]} ({rule["source_type"]}, {rule["source_origin"]})',
            "quoted_span": rule["quoted_span"], **{k: rule[k] for k in keep}}


def context_for(key, buckets):
    """Coverage-relevant summaries of the same jurisdiction's candidates in other categories."""
    return [{"category": c["category"], "source": c["source_doc_id"], "title": c["title"],
             "coverage_conditions": c["coverage_conditions"], "exemptions": c["exemptions"]}
            for (j, cat), cands in buckets.items() if j == key[0] and cat != key[1] for c in cands]


MERGES = WORK / "merges"


def merge_bucket(llm, key, rules, context, refresh=False):
    """Merged records for one bucket, cached by bucket and by the exact candidate list."""
    payload = json.dumps([rules, context], sort_keys=True)
    digest = hashlib.sha256(payload.encode()).hexdigest()[:16]
    cache = MERGES / f"{CATEGORY_CODE[key[1]]}--{key[0].replace(', ', '_').replace(' ', '_')}.json"
    if cache.exists() and not refresh:
        cached = json.loads(cache.read_text())
        if cached["digest"] == digest:
            return cached["rules"]
    merged = _merge_bucket(llm, key, rules, context)
    MERGES.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps({"digest": digest, "rules": merged}, indent=1))
    return merged


def _merge_bucket(llm, key, rules, context):
    prompt = (f"Jurisdiction: {key[0]}\nCategory: {key[1]}\n\nCandidates:\n"
              + json.dumps([summarize(i, r) for i, r in enumerate(rules)], indent=1)
              + "\n\nContext (same jurisdiction, other categories; not candidates):\n"
              + json.dumps(context, indent=1))
    result, meta = call_json(llm, MERGE_SYSTEM, prompt, MERGE_SCHEMA, max_tokens=32000)
    merged = result["rules"]
    log_call({"step": "consolidate", "bucket": list(key), "candidates": len(rules), "rules_out": len(merged),
              **meta, "groups": [{"members": m["member_indices"], "quote": m["quote_index"], "reason": m["reason"]}
                                 for m in merged]})
    for m in merged:
        m["member_indices"] = [i for i in m["member_indices"] if 0 <= i < len(rules)]
        if not 0 <= m["quote_index"] < len(rules):
            m["quote_index"] = m["member_indices"][0] if m["member_indices"] else 0
    return merged


def build_rule(rule_id, jurisdiction, level, category, merged, bucket):
    quoted = bucket[merged["quote_index"]]
    rule = {k: v for k, v in merged.items() if k not in ("member_indices", "quote_index", "reason")}
    rule.update({
        "team_rule_id": rule_id,
        "jurisdiction": jurisdiction,
        "level": level,
        "category": category,
        "quoted_span": quoted["quoted_span"],
        "source_doc_id": quoted["source_doc_id"],
        "source_url": quoted["source_url"],
        "source_type": quoted["source_type"],
        "source_origin": quoted["source_origin"],
        "retrieved_at": quoted["retrieved_at"],
        "conflict_flag": merged["conflict_type"] != "none",
        "also_supported_by": sorted({bucket[i]["source_doc_id"] for i in merged["member_indices"]}
                                    - {quoted["source_doc_id"]}),
        "merge_reason": merged["reason"],
    })
    if rule["conflict_type"] == "none":
        rule["conflict_note"] = None
    return rule


def link_precedence(rules):
    """Fill overrides/interaction between state rules that yield and local rules that displace them."""
    by_state_cat = defaultdict(list)
    for r in rules:
        if r["status"] not in ("pending", "failed"):
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


def wants_refresh(key, codes):
    if codes is None:
        return False
    name = f"{CATEGORY_CODE[key[1]]}--{key[0].replace(', ', '_').replace(' ', '_')}"
    return not codes or any(c in name for c in codes)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", nargs="*", default=None, metavar="CODE",
                        help="re-merge buckets whose cache name contains CODE (e.g. ALG--NJ); no CODE = all")
    args = parser.parse_args()

    candidates = load_candidates()
    buckets = defaultdict(list)
    for c in candidates:
        buckets[(c["jurisdiction"], c["category"])].append(c)
    print(f"{len(candidates)} candidates in {len(buckets)} buckets", file=sys.stderr)

    llm = client()
    keys = sorted(buckets)
    with ThreadPoolExecutor(max_workers=6) as pool:
        merged = dict(zip(keys, pool.map(lambda k: merge_bucket(llm, k, buckets[k], context_for(k, buckets), wants_refresh(k, args.refresh)), keys), strict=True))

    rules = []
    status_order = {"in_force": 0, "not_yet_effective": 1, "pending": 2, "failed": 3}
    for key in sorted(keys, key=lambda k: (len(k[0]) > 2, k[0], k[1])):
        jurisdiction, category = key
        level = "state" if len(jurisdiction) == 2 else "city"
        records = sorted(merged[key], key=lambda m: (status_order[m["status"]], m["citation"]))
        for n, m in enumerate(records, 1):
            rule_id = f"{JURIS_CODE[jurisdiction]}-{CATEGORY_CODE[category]}-{n:02d}"
            rules.append(build_rule(rule_id, jurisdiction, level, category, m, buckets[key]))
    link_precedence(rules)

    OUT.mkdir(exist_ok=True)
    (WORK / "rules_full.json").write_text(json.dumps(rules, indent=1))
    RULES_OUT.write_text(json.dumps({"rules": [submission_record(r) for r in rules]}, indent=1))
    print(f"wrote {len(rules)} rules to {RULES_OUT}", file=sys.stderr)


if __name__ == "__main__":
    main()
