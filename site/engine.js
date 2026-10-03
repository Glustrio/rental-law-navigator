// Browser port of navigator/engine.py. Same rules, same answers: tests/parity.mjs
// runs both on every sample address and fails if they ever disagree.

function parseDate(s, endOfPeriod = false) {
  if (!s) return null;
  const p = s.split("-").map(Number);
  if (p.length === 3) return new Date(Date.UTC(p[0], p[1] - 1, p[2]));
  if (p.length === 2) {
    return endOfPeriod ? new Date(Date.UTC(p[0], p[1], 0)) : new Date(Date.UTC(p[0], p[1] - 1, 1));
  }
  return endOfPeriod ? new Date(Date.UTC(p[0], 11, 31)) : new Date(Date.UTC(p[0], 0, 1));
}

const isoDay = (d) => d.toISOString().slice(0, 10);

function builtOnOrBefore(year, cutoff) {
  if (year == null) return null;
  const cy = cutoff.getUTCFullYear();
  if (year < cy) return true;
  if (year > cy) return false;
  return cutoff.getUTCMonth() === 11 && cutoff.getUTCDate() === 31 ? true : null;
}

function builtAfter(year, cutoff) {
  const v = builtOnOrBefore(year, cutoff);
  return v == null ? null : !v;
}

function unitsAtLeast(a, n) {
  if (a.units_low != null && a.units_low >= n) return true;
  if (a.units_high != null && a.units_high < n) return false;
  return null;
}

function unitsAtMost(a, n) {
  const v = unitsAtLeast(a, n + 1);
  return v == null ? null : !v;
}

function olderThan(a, years, asOf) {
  if (a.year_built == null) return null;
  const edge = asOf.getUTCFullYear() - years;
  if (a.year_built === edge) return null;
  return a.year_built < edge;
}

function coverageTest(rule, a, asOf) {
  const cov = rule.coverage;
  const reasons = [];
  let unknown = false;
  const check = (value, ok, fail, unk) => {
    if (value === false) { reasons.push(fail); return false; }
    if (value == null) { unknown = true; reasons.push(unk); } else reasons.push(ok);
    return true;
  };
  const yr = a.year_built;
  if (cov.min_units && !check(unitsAtLeast(a, cov.min_units), `has ${cov.min_units}+ units`,
    `fewer than ${cov.min_units} units`, `coverage needs ${cov.min_units}+ units; ${a.units_note}`)) return [false, reasons];
  if (cov.max_units && !check(unitsAtMost(a, cov.max_units), `at most ${cov.max_units} units`,
    `more than ${cov.max_units} units`, `coverage needs at most ${cov.max_units} units; ${a.units_note}`)) return [false, reasons];
  if (cov.built_on_or_before) {
    const c = parseDate(cov.built_on_or_before, true);
    if (!check(builtOnOrBefore(yr, c), `built ${yr}, on or before the ${isoDay(c)} cutoff`,
      `built ${yr}, after the ${isoDay(c)} cutoff`,
      `coverage depends on a ${isoDay(c)} certificate-of-occupancy cutoff; ` +
        (yr == null ? "year built missing" : `built in ${yr}, the cutoff year`))) return [false, reasons];
  }
  if (cov.built_after) {
    const c = parseDate(cov.built_after, true);
    if (!check(builtAfter(yr, c), `built ${yr}, after ${isoDay(c)}`, `built ${yr}, not after ${isoDay(c)}`,
      `coverage needs construction after ${isoDay(c)}; ` + (yr == null ? "year built missing" : `built in ${yr}`))) return [false, reasons];
  }
  if (cov.min_building_age_years) {
    const n = cov.min_building_age_years;
    if (!check(olderThan(a, n, asOf), `more than ${n} years old (built ${yr})`, `less than ${n} years old (built ${yr})`,
      `coverage needs a building more than ${n} years old; ` + (yr == null ? "year built missing" : `built in ${yr}, at the edge`))) return [false, reasons];
  }
  for (const cond of cov.unresolvable_conditions || []) {
    unknown = true;
    reasons.push(`depends on a fact not in the data: ${cond}`);
  }
  return [unknown ? null : true, reasons];
}

function exemptionTest(rule, a, asOf) {
  const reasons = [];
  let unknown = false;
  for (const ex of rule.exemption_tests || []) {
    const limits = [];
    if (ex.if_units_at_most != null) limits.push(unitsAtMost(a, ex.if_units_at_most));
    if (ex.if_built_after) limits.push(builtAfter(a.year_built, parseDate(ex.if_built_after, true)));
    if (ex.if_younger_than_years) {
      const older = olderThan(a, ex.if_younger_than_years, asOf);
      limits.push(older == null ? null : !older);
    }
    if (limits.some((v) => v === false)) continue;
    if (!limits.length && !ex.needs_unknown_fact) continue;
    if (limits.every((v) => v === true) && !ex.needs_unknown_fact) {
      reasons.push(`exempt: ${ex.description}`);
      return [true, reasons];
    }
    unknown = true;
    reasons.push(`may be exempt: ${ex.description}`);
  }
  return [unknown ? null : false, reasons];
}

function evaluate(rule, a, asOf) {
  if (rule.status === "failed") return [null, ["proposal failed; not law"]];
  let [covered, reasons] = coverageTest(rule, a, asOf);
  if (covered === false) return [null, reasons];
  const [exempt, exReasons] = exemptionTest(rule, a, asOf);
  reasons = reasons.concat(exReasons);
  if (exempt === true) return [null, reasons];
  if (rule.status === "pending") return ["pending", ["bill or proposal, not law", ...reasons]];
  const eff = parseDate(rule.effective_date);
  if (rule.status === "not_yet_effective" && eff == null) return ["not_yet_effective", ["enacted but not yet in effect", ...reasons]];
  if (eff && eff > asOf) return ["not_yet_effective", [`takes effect ${rule.effective_date}`, ...reasons]];
  if (covered == null || exempt == null) return ["unknown", reasons];
  return ["applies", reasons];
}

const REVIEW_CONFIDENCE = 0.7;

// Low-confidence rules and rules resting only on a secondary source go to a human.
function needsReview(rule) {
  return (rule.confidence || 0) < REVIEW_CONFIDENCE || rule.source_origin === "supplement";
}

// A state rule that yields to a local rule that displaces it is settled precedence, not a conflict.
function isPrecedence(a, b) {
  const [state, local] = a.level === "state" ? [a, b] : [b, a];
  return Boolean(state.yields_to_local_rule && local.displaces_state_rule);
}

function usesUnitCount(rule) {
  const cov = rule.coverage;
  return Boolean(cov.min_units || cov.max_units || (rule.exemption_tests || []).some((e) => e.if_units_at_most != null));
}

// Rule extraction confidence, discounted for each weaker link behind this particular answer.
function answerConfidence(rule, a, result) {
  let c = rule.confidence || 0.5;
  if (result === "unknown") c *= 0.5;
  if (a.geocode_method !== "census") c *= 0.9;
  if (a.units_note.startsWith("unit count not recorded; inferred") && usesUnitCount(rule)) c *= 0.9;
  return Math.round(c * 100) / 100;
}

function conflictFor(rule, raw, byId) {
  if (rule.conflict_type === "inconsistent_sources") return [true, [`review: ${rule.conflict_note}`]];
  // A state rule that says how it yields to local law has settled precedence.
  if (rule.conflict_type !== "preemption" || rule.yields_to_local_rule) return [false, []];
  const other = rule.level === "state" ? "city" : "state";
  const peers = Object.entries(raw)
    .filter(([id, [res]]) => res && byId[id].category === rule.category && byId[id].level === other
      && !isPrecedence(rule, byId[id]))
    .map(([id]) => id);
  if (peers.length) return [true, [`possible conflict with ${peers.join(", ")}: ${rule.conflict_note}`]];
  return [false, []];
}

const LEADS = {
  applies: (t, where) => `${t} covers this ${where} building.`,
  unknown: (t) => `${t} may cover this building, but the data can't settle it.`,
  superseded: (t) => `${t} is displaced here by a stricter local rule.`,
  not_yet_effective: (t) => `${t} is enacted but not yet in effect.`,
  pending: (t) => `${t} is a pending proposal, not law.`,
};

function explain(rule, a, result, reasons) {
  const where = a.city ? `${a.city}, ${a.state}` : a.state;
  const lead = LEADS[result](rule.title, where);
  const detail = [...new Set(reasons)].join("; ");
  return detail ? `${lead} ${detail}.` : lead;
}

export function lookup(a, rules, asOf) {
  const mine = rules.filter((r) => a.jurisdictions.includes(r.jurisdiction));
  const byId = Object.fromEntries(mine.map((r) => [r.team_rule_id, r]));
  const raw = Object.fromEntries(mine.map((r) => [r.team_rule_id, evaluate(r, a, asOf)]));
  const out = [];
  for (const rule of mine) {
    const id = rule.team_rule_id;
    let [result, reasons] = raw[id];
    if (result == null) continue;
    if (rule.level === "state" && rule.yields_to_local_rule && (result === "applies" || result === "unknown")) {
      const local = (rule.overrides || []).filter((l) => l in raw).map((l) => [l, raw[l][0]]);
      if (local.some(([, r]) => r === "applies")) {
        result = "superseded";
        reasons = local.filter(([, r]) => r === "applies").map(([l]) => `stricter local rule ${l} covers this unit`);
      } else if (local.some(([, r]) => r === "unknown")) {
        result = "unknown";
        reasons = reasons.concat(local.filter(([, r]) => r === "unknown")
          .map(([l]) => `whether local rule ${l} covers this unit instead is unknown`));
      }
    }
    const [flag, flagReasons] = conflictFor(rule, raw, byId);
    out.push({
      team_rule_id: id,
      result,
      explanation: explain(rule, a, result, reasons.concat(flagReasons)),
      reasons: [...new Set(reasons.concat(flagReasons))],
      conflict_flag: flag,
      needs_review: needsReview(rule),
      confidence: answerConfidence(rule, a, result),
    });
  }
  return out;
}

export { parseDate };
