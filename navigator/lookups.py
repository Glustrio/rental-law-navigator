"""Write out/lookups.json for all 500 addresses and the data files the website reads."""

import json
import sys
from collections import Counter
from datetime import date

from navigator.engine import load_addresses, load_rules, lookup
from navigator.paths import DEFAULT_AS_OF, LOOKUPS_OUT, SITE_DATA


def main():
    rules, addresses = load_rules(), load_addresses()
    as_of = date.fromisoformat(DEFAULT_AS_OF)
    lookups = {aid: lookup(a, rules, as_of) for aid, a in sorted(addresses.items())}
    LOOKUPS_OUT.write_text(json.dumps({"as_of": DEFAULT_AS_OF, "lookups": lookups}, indent=1))
    counts = Counter(r["result"] for rs in lookups.values() for r in rs)
    print(f"wrote {LOOKUPS_OUT}: {dict(counts)}", file=sys.stderr)

    # The site re-runs the same engine in the browser, so it needs rules and addresses.
    SITE_DATA.mkdir(parents=True, exist_ok=True)
    (SITE_DATA / "rules.json").write_text(json.dumps(rules))
    (SITE_DATA / "addresses.json").write_text(json.dumps({aid: a.as_dict() for aid, a in addresses.items()}))


if __name__ == "__main__":
    main()
