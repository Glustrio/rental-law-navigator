"""Module B: resolve an address to its jurisdiction stack and test every rule against it.

Everything here is deterministic. The model's work ends at extraction; this file only
compares building facts (year built, unit count) with each rule's coverage tests and
reports applies / unknown / superseded / not_yet_effective / pending, with the reason.
"""

import csv
import json
from dataclasses import dataclass, field
from datetime import date

from navigator.paths import ADDRESSES, DEFAULT_AS_OF, GEOCODED, WORK

STATES = {"CA", "NJ", "MA"}

# Mailing cities that sit wholly inside a legal city. Used only when the Census
# geocoder can't match an address.
POSTAL_FALLBACK = {
    ("MA", "Dorchester"): "Boston", ("MA", "Roxbury"): "Boston", ("MA", "Hyde Park"): "Boston",
    ("MA", "Mattapan"): "Boston", ("MA", "Allston"): "Boston", ("MA", "Brighton"): "Boston",
    ("MA", "East Boston"): "Boston", ("MA", "South Boston"): "Boston", ("MA", "Jamaica Plain"): "Boston",
    ("MA", "Boston"): "Boston", ("MA", "Cambridge"): "Cambridge",
    ("CA", "San Francisco"): "San Francisco",  # city and county are the same boundary
    ("NJ", "Hoboken"): "Hoboken", ("NJ", "Jersey City"): "Jersey City", ("NJ", "Newark"): "Newark",
}

# Unit ranges implied by assessor use codes, for rows without a unit count.
USE_CODE_UNITS = [
    (lambda r: r["state"] == "NJ" and r["use_code"] == "4C", (5, None), "NJ property class 4C (apartments, 5+ units)"),
    (lambda r: r["use_code"] == "A/112", (7, 30), "Boston use code 112 (apartments, 7-30 units)"),
    (lambda r: r["use_code"] == "111" and "4-8" in r["use_description"], (4, 8), "Cambridge use code 111 (4-8 units)"),
    (lambda r: r["use_code"] == "112" and ">8" in r["use_description"], (9, None), "Cambridge use code 112 (more than 8 units)"),
    (lambda r: "5+ units" in r["use_description"] or "Five or more" in r["use_description"], (5, None), "use code for 5+ unit buildings"),
    (lambda r: r["use_code"] in ("A5", "F5", "FS5"), (5, 14), "SF use code (5-14 units)"),
    (lambda r: r["use_code"] == "A15", (15, None), "SF use code (15+ units)"),
]


@dataclass
class Address:
    address_id: str
    street: str
    postal_city: str
    state: str
    zip: str
    year_built: int | None
    units_low: int | None
    units_high: int | None
    units_note: str
    use_description: str
    city: str | None
    county: str | None
    geocode_method: str
    lon: float | None = None
    lat: float | None = None
    notes: list = field(default_factory=list)

    @property
    def jurisdictions(self):
        stack = [self.state]
        if self.city:
            stack.append(f"{self.city}, {self.state}")
        return stack

    def as_dict(self):
        return {k: getattr(self, k) for k in self.__dataclass_fields__} | {"jurisdictions": self.jurisdictions}


def unit_range(row):
    if row["units"].strip():
        n = int(float(row["units"]))
        return n, n, "unit count from assessor record"
    for test, (lo, hi), note in USE_CODE_UNITS:
        if test(row):
            return lo, hi, f"unit count not recorded; inferred from {note}"
    return None, None, "unit count not recorded"


def load_addresses():
    geo = json.loads(GEOCODED.read_text())
    with open(ADDRESSES) as f:
        rows = list(csv.DictReader(f))
    out = {}
    for row in rows:
        g = geo.get(row["address_id"], {})
        notes = []
        city, method = g.get("place"), g.get("method", "unmatched")
        if g.get("state_abbr") and g["state_abbr"] != row["state"]:
            notes.append(f"geocoder placed this address in {g['state_abbr']}; using the recorded state {row['state']}")
            city = None
        if not city:
            city = POSTAL_FALLBACK.get((row["state"], row["postal_city"]))
            if city:
                method = "postal_city_fallback"
                notes.append(f"Census geocoder could not match the address; {row['postal_city']} lies entirely within {city}")
            else:
                notes.append("no incorporated city found; only state rules are tested")
        elif city != row["postal_city"]:
            notes.append(f"mailing city is {row['postal_city']}, but the parcel is inside the City of {city}")
        lo, hi, unit_note = unit_range(row)
        year = int(row["year_built"]) if row["year_built"].strip() else None
        out[row["address_id"]] = Address(
            row["address_id"], row["street_address"], row["postal_city"], row["state"], row["zip"], year,
            lo, hi, unit_note, row["use_description"], city, g.get("county"), method, g.get("lon"), g.get("lat"), notes)
    return out


# --- tri-state helpers: True, False or None (unknown) ---

def _parse_date(s, end_of_period=False):
    """'2025-06' -> 2025-06-01; '2026' -> 2026-01-01 (or period end when end_of_period)."""
    if not s:
        return None
    parts = [int(p) for p in s.split("-")]
    if len(parts) == 3:
        return date(*parts)
    if len(parts) == 2:
        if end_of_period:
            nxt = date(parts[0] + (parts[1] == 12), parts[1] % 12 + 1, 1)
            return date.fromordinal(nxt.toordinal() - 1)
        return date(parts[0], parts[1], 1)
    return date(parts[0], 12, 31) if end_of_period else date(parts[0], 1, 1)


def built_on_or_before(year, cutoff):
    """Year built is only a year, so a building from the cutoff year itself is unknown."""
    if year is None:
        return None
    if year < cutoff.year:
        return True
    if year > cutoff.year:
        return False
    return True if cutoff.month == 12 and cutoff.day == 31 else None


def built_after(year, cutoff):
    v = built_on_or_before(year, cutoff)
    return None if v is None else not v


def units_at_least(addr, n):
    if addr.units_low is not None and addr.units_low >= n:
        return True
    if addr.units_high is not None and addr.units_high < n:
        return False
    return None


def units_at_most(addr, n):
    v = units_at_least(addr, n + 1)
    return None if v is None else not v


def older_than(addr, years, as_of):
    """Certificate of occupancy more than `years` years before as_of (rolling test)."""
    if addr.year_built is None:
        return None
    edge = as_of.year - years
    if addr.year_built == edge:
        return None
    return addr.year_built < edge


def coverage_test(rule, addr, as_of):
    """Return (True | False | None, reasons) for whether the rule's own coverage reaches this building."""
    cov = rule["coverage"]
    reasons, unknown = [], False

    def check(value, ok_text, fail_text, unknown_text):
        nonlocal unknown
        if value is False:
            reasons.append(fail_text)
            return False
        if value is None:
            unknown = True
            reasons.append(unknown_text)
        else:
            reasons.append(ok_text)
        return True

    if cov.get("min_units") and not check(units_at_least(addr, cov["min_units"]),
                                           f"has {cov['min_units']}+ units", f"fewer than {cov['min_units']} units",
                                           f"coverage needs {cov['min_units']}+ units; {addr.units_note}"):
        return False, reasons
    if cov.get("max_units") and not check(units_at_most(addr, cov["max_units"]),
                                           f"at most {cov['max_units']} units", f"more than {cov['max_units']} units",
                                           f"coverage needs at most {cov['max_units']} units; {addr.units_note}"):
        return False, reasons
    if cov.get("built_on_or_before"):
        cutoff = _parse_date(cov["built_on_or_before"], end_of_period=True)
        yr = addr.year_built
        if not check(built_on_or_before(yr, cutoff), f"built {yr}, on or before the {cutoff} cutoff",
                     f"built {yr}, after the {cutoff} cutoff",
                     f"coverage depends on a {cutoff} certificate-of-occupancy cutoff; "
                     + ("year built missing" if yr is None else f"built in {yr}, the cutoff year")):
            return False, reasons
    if cov.get("built_after"):
        cutoff = _parse_date(cov["built_after"], end_of_period=True)
        yr = addr.year_built
        if not check(built_after(yr, cutoff), f"built {yr}, after {cutoff}", f"built {yr}, not after {cutoff}",
                     f"coverage needs construction after {cutoff}; "
                     + ("year built missing" if yr is None else f"built in {yr}")):
            return False, reasons
    if cov.get("min_building_age_years"):
        n, yr = cov["min_building_age_years"], addr.year_built
        if not check(older_than(addr, n, as_of), f"more than {n} years old (built {yr})",
                     f"less than {n} years old (built {yr})",
                     f"coverage needs a building more than {n} years old; "
                     + ("year built missing" if yr is None else f"built in {yr}, at the edge")):
            return False, reasons
    for cond in cov.get("unresolvable_conditions") or []:
        unknown = True
        reasons.append(f"depends on a fact not in the data: {cond}")
    return (None if unknown else True), reasons


def exemption_test(rule, addr, as_of):
    """(True | False | None, reasons): does any exemption take this building out?"""
    reasons, unknown = [], False
    for ex in rule.get("exemption_tests") or []:
        limits = []
        if ex.get("if_units_at_most") is not None:
            limits.append(units_at_most(addr, ex["if_units_at_most"]))
        if ex.get("if_built_after"):
            limits.append(built_after(addr.year_built, _parse_date(ex["if_built_after"], end_of_period=True)))
        if ex.get("if_younger_than_years"):
            older = older_than(addr, ex["if_younger_than_years"], as_of)
            limits.append(None if older is None else not older)
        if any(v is False for v in limits):
            continue  # this exemption can't reach the building
        if not limits and not ex.get("needs_unknown_fact"):
            continue  # a qualitative exemption with no test we can run; noted in the rule text
        if all(v is True for v in limits) and not ex.get("needs_unknown_fact"):
            reasons.append(f"exempt: {ex['description']}")
            return True, reasons
        unknown = True
        reasons.append(f"may be exempt: {ex['description']}")
    return (None if unknown else False), reasons


def evaluate(rule, addr, as_of):
    """Raw result before state/local precedence: 'applies', 'unknown', 'pending', 'not_yet_effective' or None."""
    if rule["status"] == "failed":
        return None, ["proposal failed; not law"]
    covered, reasons = coverage_test(rule, addr, as_of)
    if covered is False:
        return None, reasons
    exempt, ex_reasons = exemption_test(rule, addr, as_of)
    reasons += ex_reasons
    if exempt is True:
        return None, reasons
    if rule["status"] == "pending":
        return "pending", ["bill or proposal, not law"] + reasons
    eff = _parse_date(rule.get("effective_date"))
    if rule["status"] == "not_yet_effective" and eff is None:
        return "not_yet_effective", ["enacted but not yet in effect"] + reasons
    if eff and eff > as_of:
        return "not_yet_effective", [f"takes effect {rule['effective_date']}"] + reasons
    if covered is None or exempt is None:
        return "unknown", reasons
    return "applies", reasons


def lookup(addr, rules, as_of=None):
    """All rules for an address on a date, with precedence and conflict flags applied."""
    as_of = as_of or date.fromisoformat(DEFAULT_AS_OF)
    mine = [r for r in rules if r["jurisdiction"] in addr.jurisdictions]
    raw = {r["team_rule_id"]: evaluate(r, addr, as_of) for r in mine}
    by_id = {r["team_rule_id"]: r for r in mine}
    results = []
    for rule in mine:
        rid = rule["team_rule_id"]
        result, reasons = raw[rid]
        if result is None:
            continue
        if rule["level"] == "state" and rule.get("yields_to_local_rule") and result in ("applies", "unknown"):
            local = [(lid, raw[lid][0]) for lid in rule.get("overrides", []) if lid in raw]
            if any(res == "applies" for _, res in local):
                result = "superseded"
                reasons = [f"stricter local rule {lid} covers this unit" for lid, res in local if res == "applies"]
            elif any(res == "unknown" for _, res in local):
                result = "unknown"
                reasons = reasons + [f"whether local rule {lid} covers this unit instead is unknown"
                                     for lid, res in local if res == "unknown"]
        flag, flag_reasons = conflict_for(rule, addr, raw, by_id)
        results.append({
            "team_rule_id": rid,
            "result": result,
            "explanation": explain(rule, addr, result, reasons + flag_reasons),
            "conflict_flag": flag,
            "needs_review": needs_review(rule),
        })
    return results


REVIEW_CONFIDENCE = 0.7


def needs_review(rule):
    """Low-confidence rules and rules resting only on a secondary source go to a human."""
    return (rule.get("confidence") or 0) < REVIEW_CONFIDENCE or rule.get("source_origin") == "supplement"


def is_precedence(a, b):
    """A state rule that yields to a local rule that displaces it is settled precedence, not a conflict."""
    state, local = (a, b) if a["level"] == "state" else (b, a)
    return bool(state.get("yields_to_local_rule") and local.get("displaces_state_rule"))


def conflict_for(rule, addr, raw, by_id):
    """Preemption conflicts flag only where both sides reach the address; source conflicts flag everywhere."""
    if rule.get("conflict_type") == "inconsistent_sources":
        return True, [f"review: {rule.get('conflict_note')}"]
    if rule.get("conflict_type") != "preemption" or rule.get("yields_to_local_rule"):
        return False, []  # a state rule that says how it yields to local law has settled precedence
    other_level = "city" if rule["level"] == "state" else "state"
    peers = [rid for rid, (res, _) in raw.items()
             if res and by_id[rid]["category"] == rule["category"] and by_id[rid]["level"] == other_level
             and not is_precedence(rule, by_id[rid])]
    if peers:
        return True, [f"possible conflict with {', '.join(peers)}: {rule.get('conflict_note')}"]
    return False, []


def explain(rule, addr, result, reasons):
    where = f"{addr.city}, {addr.state}" if addr.city else addr.state
    lead = {
        "applies": f"{rule['title']} covers this {where} building.",
        "unknown": f"{rule['title']} may cover this building, but the data can't settle it.",
        "superseded": f"{rule['title']} is displaced here by a stricter local rule.",
        "not_yet_effective": f"{rule['title']} is enacted but not yet in effect.",
        "pending": f"{rule['title']} is a pending proposal, not law.",
    }[result]
    detail = "; ".join(dict.fromkeys(reasons))
    return f"{lead} {detail}." if detail else lead


def load_rules():
    return json.loads((WORK / "rules_full.json").read_text())
