"""Renter-facing text for each rule, in English and Spanish.

For every rule Claude writes a one-line "what this means for you", a hint naming the
document or fact that would settle an "unknown" answer, and Spanish versions of the
title, requirement and both lines. Results are cached by the rule's content, so only
new or changed rules cost a model call. Written to work/plain_language.json.
"""

import hashlib
import json
import sys
from concurrent.futures import ThreadPoolExecutor

from navigator.extract import log_call
from navigator.llm import call_json, client
from navigator.paths import WORK

CACHE = WORK / "plain_language.json"
BATCH = 8

FIELDS = ["summary_en", "settle_hint_en", "title_es", "requirement_es", "key_value_es", "summary_es", "settle_hint_es"]

SCHEMA = {
    "type": "object",
    "properties": {
        "rules": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"team_rule_id": {"type": "string"},
                               **{f: {"type": ["string", "null"]} for f in FIELDS}},
                "required": ["team_rule_id", *FIELDS],
                "additionalProperties": False,
            },
        }
    },
    "required": ["rules"],
    "additionalProperties": False,
}

SYSTEM = """You write plain-language housing information for renters, in English and Spanish.

For each rule record:
- summary_en: one sentence, at most 25 words, telling a renter what the rule means for them
  ("Your landlord can raise rent by at most ..."). Concrete numbers when the record has them.
  For a pending bill or failed proposal, say plainly that it is not law. Never give legal advice,
  never suggest ways to avoid a rule, never add facts the record does not state.
- settle_hint_en: one sentence naming the document or fact that would settle whether the rule covers
  a particular building (e.g. "The building's certificate of occupancy date, from the city building
  department."). Null if coverage never depends on building facts.
- title_es, requirement_es, key_value_es, summary_es, settle_hint_es: natural Latin American Spanish
  translations of the title, requirement, key_value, summary_en and settle_hint_en. Keep legal citations,
  numbers and proper names unchanged. Null where the English is null.
Use simple words a sixth grader can follow in both languages.
"""


def rule_key(rule):
    keep = {k: rule.get(k) for k in ("title", "requirement", "key_value", "status", "coverage_conditions",
                                     "exemptions", "coverage", "effective_date")}
    return hashlib.sha256(json.dumps(keep, sort_keys=True).encode()).hexdigest()[:16]


def brief(rule):
    return {k: rule.get(k) for k in ("team_rule_id", "jurisdiction", "category", "status", "title", "requirement",
                                     "key_value", "coverage_conditions", "exemptions", "effective_date")}


def run_batch(llm, batch):
    result, meta = call_json(llm, SYSTEM, json.dumps([brief(r) for r in batch], indent=1), SCHEMA,
                             max_tokens=16000, effort="medium")
    log_call({"step": "plain_language", "rules": [r["team_rule_id"] for r in batch], **meta})
    return result["rules"]


def main():
    rules = json.loads((WORK / "rules_full.json").read_text())
    cache = json.loads(CACHE.read_text()) if CACHE.exists() else {}
    todo = [r for r in rules if cache.get(r["team_rule_id"], {}).get("key") != rule_key(r)]
    print(f"{len(todo)} of {len(rules)} rules need plain-language text", file=sys.stderr)
    batches = [todo[i:i + BATCH] for i in range(0, len(todo), BATCH)]
    if batches:
        llm = client()
        with ThreadPoolExecutor(max_workers=4) as pool:
            for out in pool.map(lambda b: run_batch(llm, b), batches):
                for item in out:
                    rid = item.pop("team_rule_id")
                    rule = next((r for r in rules if r["team_rule_id"] == rid), None)
                    if rule:
                        cache[rid] = {"key": rule_key(rule), **item}
    CACHE.write_text(json.dumps(cache, indent=1, ensure_ascii=False))
    missing = [r["team_rule_id"] for r in rules if r["team_rule_id"] not in cache]
    print(f"wrote {CACHE}" + (f"; missing {missing}" if missing else ""), file=sys.stderr)


if __name__ == "__main__":
    main()
