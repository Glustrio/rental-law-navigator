"""Copy the outputs the website needs into site/data and write the method page."""

import html
import json
import sys
from collections import Counter

from navigator.changes import load_tests
from navigator.paths import AUDIT_LOG, CHANGES_OUT, LOOKUPS_OUT, SITE_DATA, WORK


def audit_summary():
    calls = [json.loads(line) for line in AUDIT_LOG.read_text().splitlines()] if AUDIT_LOG.exists() else []
    steps = Counter(c["step"] for c in calls)
    tokens_in = sum(c.get("input_tokens", 0) for c in calls)
    tokens_out = sum(c.get("output_tokens", 0) for c in calls)
    dropped = sum(c.get("rules_dropped", 0) for c in calls if c["step"] == "extract")
    return steps, tokens_in, tokens_out, dropped


def method_html(rules, lookups):
    steps, tin, tout, dropped = audit_summary()
    results = Counter(r["result"] for rs in lookups["lookups"].values() for r in rs)
    statuses = Counter(r["status"] for r in rules)
    secondary = sum(r.get("source_origin") == "supplement" for r in rules)
    e = html.escape
    return f"""
<div class="card">
  <h3>Pipeline</h3>
  <ol>
    <li><strong>Extract.</strong> Claude reads each of the {steps.get('extract', 0)} documents and returns rule records in the challenge schema, plus machine-checkable coverage tests (unit counts, construction cutoffs, rolling age tests, exemptions). Every quoted span is located in the source text; {dropped} candidate rules were dropped because their quote could not be found verbatim.</li>
    <li><strong>Consolidate.</strong> Candidates describing the same law in different documents are merged, keeping the best official source and its exact quote. Disagreeing dates are kept and flagged rather than silently resolved.</li>
    <li><strong>Resolve.</strong> Each address is geocoded with the Census Geocoder and placed in its legal city, not its mailing city. Missing unit counts are inferred only where the assessor use code states a range.</li>
    <li><strong>Apply.</strong> A deterministic engine (no AI) tests each rule's coverage against the building facts on the chosen date and reports applies, unknown, superseded, not yet effective or pending, with its reasoning.</li>
    <li><strong>Track change.</strong> Change tests are mapped to our rules once, then evaluated by the same engine at each date.</li>
  </ol>
</div>
<div class="card">
  <h3>Numbers</h3>
  <p>{len(rules)} rules ({', '.join(f'{n} {e(k)}' for k, n in statuses.items())}); {secondary} rely on a secondary source because the official text is not in the corpus.</p>
  <p>Lookup results for 500 addresses on {e(lookups['as_of'])}: {', '.join(f'{n} {e(k)}' for k, n in results.most_common())}.</p>
  <p>{sum(steps.values())} model calls logged ({tin:,} input / {tout:,} output tokens). The audit log records every call, its inputs' hashes and outputs.</p>
</div>
<div class="card">
  <h3>Guardrails</h3>
  <ul>
    <li>A rule is only reported if a sentence from its source supports it, copied verbatim.</li>
    <li>When coverage turns on a fact the data lacks (owner type, exact certificate-of-occupancy date), the answer is "unknown", never a guess.</li>
    <li>Pending bills and failed proposals are kept separate from law in force.</li>
    <li>Possible preemption (a state law that may override city ordinances) and conflicting published dates are flagged for human review.</li>
    <li>The tool explains rules; it does not advise on avoiding them, and it is not legal advice.</li>
  </ul>
</div>
<div class="card">
  <h3>Extending to a new city</h3>
  <p>Add the city's ordinance text to the corpus and its name to the jurisdiction list, then rerun extraction for the new documents. The engine and site need no changes: coverage tests are data, not code.</p>
</div>"""


def main():
    rules = json.loads((WORK / "rules_full.json").read_text())
    lookups = json.loads(LOOKUPS_OUT.read_text())
    SITE_DATA.mkdir(parents=True, exist_ok=True)
    (SITE_DATA / "changes.json").write_text(CHANGES_OUT.read_text() if CHANGES_OUT.exists() else "{}")
    (SITE_DATA / "tests.json").write_text(json.dumps(load_tests()))
    (SITE_DATA / "method.json").write_text(json.dumps({"html": method_html(rules, lookups)}))
    print(f"site data written to {SITE_DATA}", file=sys.stderr)


if __name__ == "__main__":
    main()
