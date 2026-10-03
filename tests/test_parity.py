"""The site's JavaScript engine must give the same answers as the Python engine."""

import json
import shutil
import subprocess
from datetime import date
from pathlib import Path

import pytest

from navigator.engine import load_addresses, lookup
from navigator.paths import GEOCODED, WORK
from tests.test_engine import SF_RENT, STATE_CAP, rule

ROOT = Path(__file__).resolve().parent.parent
DATES = ["2025-12-31", "2026-01-02", "2026-10-01", "2027-07-02"]


def fixture_rules():
    ex = {"description": "small landlord", "if_units_at_most": 4, "if_built_after": None,
          "if_younger_than_years": None, "needs_unknown_fact": True}
    return [
        STATE_CAP, SF_RENT,
        rule("CA-DEP", "CA", "state", category="security_deposits", exemptions=[ex]),
        rule("CA-ALG", "CA", "state", category="algorithmic_rent_setting", effective="2026-01-01"),
        rule("NJ-ALG", "NJ", "state", category="algorithmic_rent_setting", effective="2027-07-01", conflict="preemption"),
        rule("JC-ALG", "Jersey City, NJ", "city", category="algorithmic_rent_setting"),
        rule("JC-RENT", "Jersey City, NJ", "city", coverage={"min_units": 5}),
        rule("MA-P", "MA", "state", status="pending"),
    ]


@pytest.mark.skipif(not shutil.which("node") or not GEOCODED.exists(), reason="needs node and geocoded addresses")
@pytest.mark.parametrize("source", ["fixture", "extracted"])
def test_js_engine_matches_python(tmp_path, source):
    if source == "fixture":
        rules = fixture_rules()
    else:
        path = WORK / "rules_full.json"
        if not path.exists():
            pytest.skip("no extracted rules yet")
        rules = json.loads(path.read_text())
    addresses = load_addresses()
    case = tmp_path / "case.json"
    case.write_text(json.dumps({"rules": rules, "dates": DATES,
                                "addresses": {k: a.as_dict() for k, a in addresses.items()}}))
    js = json.loads(subprocess.run(["node", str(ROOT / "tests" / "parity.mjs"), str(case)],
                                   capture_output=True, text=True, check=True).stdout)
    for d in DATES:
        for aid, a in addresses.items():
            assert js[d][aid] == lookup(a, rules, date.fromisoformat(d)), (d, aid)
