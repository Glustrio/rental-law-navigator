"""Module C: run the change-tracking tests and write out/changes.json.

Each test names rules by the organizers' ids (e.g. CA-ALG-01), which are not our ids.
Claude maps each test to our extracted rules once (logged); the affected-address sets
are then computed by the deterministic lookup engine at the dates each test asks for.
"""

import json
import sys
from datetime import date

from navigator.engine import load_addresses, load_rules, lookup
from navigator.extract import log_call
from navigator.llm import call_json, client
from navigator.paths import CHANGE_TESTS, CHANGES_OUT, DEFAULT_AS_OF, EXTRA_DOCS, WORK

MAPPING_CACHE = WORK / "test_rule_mapping.json"

MAP_SCHEMA = {
    "type": "object",
    "properties": {
        "mappings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "test_id": {"type": "string"},
                    "our_rule_ids": {"type": "array", "items": {"type": "string"}},
                    "conflict_rule_ids": {"type": "array", "items": {"type": "string"}},
                    "reason": {"type": "string"},
                },
                "required": ["test_id", "our_rule_ids", "conflict_rule_ids", "reason"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["mappings"],
    "additionalProperties": False,
}

MAP_SYSTEM = """You match change-tracking test cases to rule records.

Each test refers to rules by an external id and describes the law it checks. For each test,
list our team_rule_ids for the same law(s), in the same order as the test's rule_ids, and in
conflict_rule_ids our ids for any rules the test says to check for conflicts. Use only ids from
the list given. If no rule of ours matches, return an empty list and say why.
"""


def rule_index(rules):
    return [{"team_rule_id": r["team_rule_id"], "jurisdiction": r["jurisdiction"], "category": r["category"],
             "status": r["status"], "title": r["title"], "citation": r["citation"],
             "effective_date": r["effective_date"]} for r in rules]


def map_tests(tests, rules, refresh=False):
    cache = json.loads(MAPPING_CACHE.read_text()) if MAPPING_CACHE.exists() and not refresh else {}
    todo = [t for t in tests if t["test_id"] not in cache]
    if todo:
        prompt = ("Tests:\n" + json.dumps(todo, indent=1) + "\n\nOur rules:\n" + json.dumps(rule_index(rules), indent=1))
        result, meta = call_json(client(), MAP_SYSTEM, prompt, MAP_SCHEMA, max_tokens=8000, effort="medium")
        log_call({"step": "map_tests", **meta, "mappings": result["mappings"]})
        known = {r["team_rule_id"] for r in rules}
        for m in result["mappings"]:
            m["our_rule_ids"] = [i for i in m["our_rule_ids"] if i in known]
            m["conflict_rule_ids"] = [i for i in m["conflict_rule_ids"] if i in known]
            cache[m["test_id"]] = m
        MAPPING_CACHE.write_text(json.dumps(cache, indent=1))
    return cache


def results_on(addresses, rules, when):
    return {aid: {r["team_rule_id"]: r for r in lookup(a, rules, when)} for aid, a in addresses.items()}


def run_test(test, mapping, addresses, rules):
    ids = mapping["our_rule_ids"]
    out = {"affected_address_ids": [], "conflict_flag_address_ids": [], "our_rule_ids": ids,
           "mapping_reason": mapping["reason"], "before_after": {}}
    if not ids:
        out["notes"] = f"No extracted rule matches this test: {mapping['reason']}"
        return out

    if test["type"] == "as_of":
        before, after = date.fromisoformat(test["as_of_before"]), date.fromisoformat(test["as_of_after"])
        res_before, res_after = results_on(addresses, rules, before), results_on(addresses, rules, after)
        for aid in addresses:
            b = {i: res_before[aid][i]["result"] for i in ids if i in res_before[aid]}
            a = {i: res_after[aid][i]["result"] for i in ids if i in res_after[aid]}
            if b != a:
                out["affected_address_ids"].append(aid)
                out["before_after"][aid] = {"before": b, "after": a}
            if any(res_before[aid][i]["conflict_flag"] or res_after[aid].get(i, {}).get("conflict_flag")
                   for i in ids if i in res_before[aid]):
                out["conflict_flag_address_ids"].append(aid)
        out["notes"] = (f"Results for {', '.join(ids)} compared on {before} and {after}. "
                        f"{len(out['affected_address_ids'])} addresses change.")
    else:
        when = date.fromisoformat(test.get("as_of", DEFAULT_AS_OF))
        res = results_on(addresses, rules, when)
        for aid in addresses:
            hits = {i: res[aid][i]["result"] for i in ids if i in res[aid]}
            if test["type"] == "pending":
                hit = any(v == "pending" for v in hits.values())
            elif test["type"] == "negative":
                hit = any(v in ("applies", "unknown", "superseded") for v in hits.values())
            else:
                hit = any(v in ("applies", "unknown", "superseded", "not_yet_effective") for v in hits.values())
            if hit:
                out["affected_address_ids"].append(aid)
                out["before_after"][aid] = {"before": {}, "after": hits}
            if any(res[aid][i]["conflict_flag"] for i in hits):
                out["conflict_flag_address_ids"].append(aid)
        out["notes"] = {
            "pending": f"{', '.join(ids)} reported as pending, never in force; affected = addresses covered if enacted.",
            "negative": f"{', '.join(ids)} is not law on {when}; no address gets it.",
        }.get(test["type"], f"Addresses covered by {', '.join(ids)} on {when}.")
        out["notes"] += f" {len(out['affected_address_ids'])} addresses."
    return out


def load_tests():
    tests = json.loads(CHANGE_TESTS.read_text())
    for path in sorted(EXTRA_DOCS.glob("*tests*.json")) if EXTRA_DOCS.exists() else []:
        tests.extend(json.loads(path.read_text()))
    return tests


def main():
    refresh = "--refresh" in sys.argv
    rules, addresses, tests = load_rules(), load_addresses(), load_tests()
    mapping = map_tests(tests, rules, refresh)
    out = {t["test_id"]: run_test(t, mapping[t["test_id"]], addresses, rules) for t in tests}
    CHANGES_OUT.write_text(json.dumps(out, indent=1))
    for tid, r in out.items():
        print(f"{tid}: {len(r['affected_address_ids'])} affected, {len(r['conflict_flag_address_ids'])} flagged "
              f"({', '.join(r['our_rule_ids']) or 'no rule'})", file=sys.stderr)


if __name__ == "__main__":
    main()
