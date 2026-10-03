from datetime import date

from navigator.engine import Address, lookup

AS_OF = date(2026, 10, 1)


def rule(rid, jurisdiction, level, category="rent_increase_limits", status="in_force", effective=None,
         coverage=None, exemptions=(), yields=False, displaces=False, overrides=(), conflict="none"):
    cov = {"min_units": None, "max_units": None, "built_on_or_before": None, "built_after": None,
           "min_building_age_years": None, "unresolvable_conditions": []}
    cov.update(coverage or {})
    return {"team_rule_id": rid, "jurisdiction": jurisdiction, "level": level, "category": category,
            "status": status, "title": rid, "effective_date": effective, "coverage": cov,
            "exemption_tests": list(exemptions), "yields_to_local_rule": yields, "displaces_state_rule": displaces,
            "overrides": list(overrides), "conflict_type": conflict, "conflict_note": "note"}


def addr(year=1960, units=(20, 20), city="San Francisco", state="CA"):
    return Address("A9999", "1 Test St", city, state, "", year, units[0], units[1], "test", "", city, None, "census")


STATE_CAP = rule("CA-RENT", "CA", "state", coverage={"min_building_age_years": 15}, yields=True, overrides=["SF-RENT"])
SF_RENT = rule("SF-RENT", "San Francisco, CA", "city", coverage={"built_on_or_before": "1979-06-13"},
               displaces=True, overrides=["CA-RENT"])


def results(a, rules, when=AS_OF):
    return {r["team_rule_id"]: r["result"] for r in lookup(a, rules, when)}


def test_local_rent_control_supersedes_state_cap():
    assert results(addr(year=1960), [STATE_CAP, SF_RENT]) == {"CA-RENT": "superseded", "SF-RENT": "applies"}


def test_newer_building_gets_state_cap_only():
    assert results(addr(year=1990), [STATE_CAP, SF_RENT]) == {"CA-RENT": "applies"}


def test_cutoff_year_is_unknown_and_makes_state_cap_unknown():
    assert results(addr(year=1979), [STATE_CAP, SF_RENT]) == {"CA-RENT": "unknown", "SF-RENT": "unknown"}


def test_rolling_age_test():
    assert results(addr(year=2020), [STATE_CAP]) == {}
    assert results(addr(year=2011), [STATE_CAP]) == {"CA-RENT": "unknown"}
    assert results(addr(year=None), [STATE_CAP]) == {"CA-RENT": "unknown"}


def test_other_city_rules_do_not_leak():
    assert results(addr(city="Los Angeles"), [SF_RENT]) == {}


def test_effective_date_switches_result():
    alg = rule("CA-ALG", "CA", "state", category="algorithmic_rent_setting", effective="2026-01-01")
    assert results(addr(), [alg], date(2025, 12, 31)) == {"CA-ALG": "not_yet_effective"}
    assert results(addr(), [alg], date(2026, 1, 2)) == {"CA-ALG": "applies"}


def test_pending_and_failed():
    pending = rule("MA-P", "MA", "state", status="pending")
    failed = rule("MA-F", "MA", "state", status="failed")
    a = addr(city="Boston", state="MA")
    assert results(a, [pending, failed]) == {"MA-P": "pending"}


def test_small_landlord_exemption_only_matters_for_small_buildings():
    ex = {"description": "small landlord", "if_units_at_most": 4, "if_built_after": None,
          "if_younger_than_years": None, "needs_unknown_fact": True}
    dep = rule("CA-DEP", "CA", "state", category="security_deposits", exemptions=[ex])
    assert results(addr(units=(20, 20)), [dep]) == {"CA-DEP": "applies"}
    assert results(addr(units=(4, 4)), [dep]) == {"CA-DEP": "unknown"}
    assert results(addr(units=(None, None)), [dep]) == {"CA-DEP": "unknown"}


def test_unit_range_from_use_code():
    jc = rule("JC-RENT", "Jersey City, NJ", "city", coverage={"min_units": 5})
    a = addr(city="Jersey City", state="NJ", units=(5, None))
    assert results(a, [jc]) == {"JC-RENT": "applies"}
    assert results(addr(city="Jersey City", state="NJ", units=(4, 8)), [jc]) == {"JC-RENT": "unknown"}


def test_preemption_flag_only_where_both_levels_reach():
    state_alg = rule("NJ-ALG", "NJ", "state", category="algorithmic_rent_setting", effective="2027-07-01",
                     conflict="preemption")
    jc_alg = rule("JC-ALG", "Jersey City, NJ", "city", category="algorithmic_rent_setting")
    jc = {r["team_rule_id"]: r for r in lookup(addr(city="Jersey City", state="NJ"), [state_alg, jc_alg], AS_OF)}
    newark = {r["team_rule_id"]: r for r in lookup(addr(city="Newark", state="NJ"), [state_alg, jc_alg], AS_OF)}
    assert jc["NJ-ALG"]["result"] == "not_yet_effective" and jc["NJ-ALG"]["conflict_flag"]
    assert newark["NJ-ALG"]["result"] == "not_yet_effective" and not newark["NJ-ALG"]["conflict_flag"]
