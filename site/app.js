import { lookup, parseDate } from "./engine.js";

const CATEGORY_LABELS = {
  rent_increase_limits: "Rent increases",
  just_cause_eviction: "Just-cause eviction",
  security_deposits: "Security deposits",
  application_screening_fees: "Application and screening fees",
  screening_restrictions: "Screening restrictions",
  algorithmic_rent_setting: "Algorithmic rent-setting",
};
const RESULT_LABELS = {
  applies: "Applies",
  unknown: "Unknown",
  superseded: "Superseded",
  not_yet_effective: "Not yet effective",
  pending: "Pending bill",
  failed: "Failed",
  in_force: "In force",
};
const EXAMPLES = ["A0002", "A0001", "A0009", "A0005"];

const $ = (sel) => document.querySelector(sel);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

const state = { rules: [], byId: {}, addresses: {}, labelToId: {}, current: null };

async function loadJSON(path) {
  const res = await fetch(path);
  if (!res.ok) throw new Error(`${path}: ${res.status}`);
  return res.json();
}

function addressLabel(a) {
  return `${a.street}, ${a.postal_city}, ${a.state} (${a.address_id})`;
}

function badge(result) {
  return `<span class="badge ${result}">${RESULT_LABELS[result] || result}</span>`;
}

function sourceLine(rule) {
  const secondary = rule.source_origin === "supplement" ? " · secondary source, official text not in corpus" : "";
  return `<a href="${esc(rule.source_url)}" target="_blank" rel="noopener">${esc(rule.source_doc_id)}</a>, retrieved ${esc(rule.retrieved_at)}${secondary}`;
}

function renderLookup() {
  const out = $("#result");
  const a = state.current;
  if (!a) return;
  const asOfValue = $("#asof").value || "2026-10-01";
  const asOf = parseDate(asOfValue);
  const results = lookup(a, state.rules, asOf);

  const crumbs = a.jurisdictions.map((j) => (j.length === 2 ? { CA: "California", NJ: "New Jersey", MA: "Massachusetts" }[j] : j.split(",")[0]));
  const counts = {};
  results.forEach((r) => { counts[r.result] = (counts[r.result] || 0) + 1; });

  let html = `
    <div class="card stack">
      <div>
        <div class="label">Address</div>
        <h2>${esc(a.street)}</h2>
        <div>${esc(a.postal_city)}, ${esc(a.state)} ${esc(a.zip)}</div>
      </div>
      <div>
        <div class="label">Jurisdictions that make the rules here</div>
        <div class="crumbs">${crumbs.map(esc).join(" › ")}</div>
        ${a.county ? `<div class="note">${esc(a.county)}</div>` : ""}
        <div class="note">Located by ${a.geocode_method === "census" ? "Census Geocoder" : esc(a.geocode_method.replaceAll("_", " "))}.</div>
        ${a.notes.map((n) => `<div class="note">${esc(n)}.</div>`).join("")}
      </div>
      <div>
        <div class="label">Building facts</div>
        <div>Built: ${a.year_built ?? "<em>not recorded</em>"}</div>
        <div>Units: ${a.units_low != null && a.units_low === a.units_high ? a.units_low : a.units_low != null ? `${a.units_low}${a.units_high ? `–${a.units_high}` : "+"} (inferred)` : "<em>not recorded</em>"}</div>
        <div class="note">${esc(a.units_note)}. ${esc(a.use_description)}</div>
      </div>
    </div>
    <p class="note">Answer as of <strong>${esc(asOfValue)}</strong>. Owner type is never in the data, so rules that turn on it say "unknown".</p>
    <div class="summary-bar">${Object.entries(counts).map(([k, n]) => `${badge(k)} <span class="note">${n}</span>`).join(" ")}</div>`;

  const byCat = {};
  results.forEach((r) => {
    const rule = state.byId[r.team_rule_id];
    (byCat[rule.category] ||= []).push([r, rule]);
  });
  for (const cat of Object.keys(CATEGORY_LABELS)) {
    html += `<h3 class="cat">${CATEGORY_LABELS[cat]}</h3>`;
    const items = byCat[cat] || [];
    if (!items.length) {
      html += `<div class="card note">No rule in this category reaches this address in our extracted law (state or city level).</div>`;
      continue;
    }
    for (const [r, rule] of items) html += ruleCard(rule, r);
  }
  out.innerHTML = html;
}

function ruleCard(rule, r) {
  const conflict = r && r.conflict_flag
    ? `<div class="flagbox"><strong>Flagged for human review.</strong> ${esc(rule.conflict_note)}</div>` : "";
  return `
    <article class="card rule">
      <div class="rule-head">
        <h4>${esc(rule.title)}</h4>
        <div>${r ? badge(r.result) : badge(rule.status)} ${r && r.conflict_flag ? '<span class="badge flag">Conflict</span>' : ""} ${r && r.needs_review ? '<span class="badge unknown">Needs review</span>' : ""}</div>
      </div>
      <p class="req">${esc(rule.requirement)}</p>
      ${r ? `<p class="why">${esc(r.explanation)}</p>` : ""}
      <div class="meta">
        <span><code>${esc(rule.citation)}</code></span>
        <span>${esc(rule.jurisdiction)} · ${rule.level}</span>
        ${rule.effective_date ? `<span>Effective ${esc(rule.effective_date)}</span>` : ""}
        ${rule.key_value ? `<span>Key value: ${esc(rule.key_value)}</span>` : ""}
        <span>Confidence ${Math.round((rule.confidence ?? 0) * 100)}%</span>
      </div>
      ${conflict}
      ${r && r.needs_review ? `<div class="flagbox"><strong>Needs human review.</strong> ${rule.source_origin === "supplement" ? "The official text is not in the corpus; this rule comes from a secondary source." : "The extraction is low-confidence."}</div>` : ""}
      <details>
        <summary>Source text and coverage</summary>
        <blockquote>${esc(rule.quoted_span)}</blockquote>
        <div class="note">Source: ${sourceLine(rule)}</div>
        <p><strong>Covers:</strong> ${esc(rule.coverage_conditions)}</p>
        ${rule.exemptions ? `<p><strong>Exemptions:</strong> ${esc(rule.exemptions)}</p>` : ""}
        ${rule.interaction ? `<p><strong>Precedence:</strong> ${esc(rule.interaction)}</p>` : ""}
        <p class="note">Rule id ${esc(rule.team_rule_id)}${rule.also_supported_by?.length ? ` · also described in ${rule.also_supported_by.map(esc).join(", ")}` : ""}</p>
      </details>
    </article>`;
}

function renderRules() {
  const j = $("#f-juris").value, c = $("#f-cat").value, s = $("#f-status").value;
  const list = state.rules.filter((r) => (!j || r.jurisdiction === j) && (!c || r.category === c) && (!s || r.status === s));
  $("#rules").innerHTML = `<p class="note">${list.length} of ${state.rules.length} rules extracted from the corpus.</p>` + list.map((r) => ruleCard(r, null)).join("");
}

function renderChanges(changes, tests) {
  const byState = (ids) => {
    const tally = {};
    ids.forEach((id) => {
      const a = state.addresses[id];
      const key = a.city ? `${a.city}, ${a.state}` : a.state;
      tally[key] = (tally[key] || 0) + 1;
    });
    return Object.entries(tally).map(([k, n]) => `<span>${esc(k)}: ${n}</span>`).join("");
  };
  $("#changes").innerHTML = tests.map((t) => {
    const c = changes[t.test_id] || { affected_address_ids: [], conflict_flag_address_ids: [], our_rule_ids: [], notes: "Not run." };
    const rules = c.our_rule_ids.map((id) => state.byId[id]).filter(Boolean);
    return `
      <article class="card test">
        <h4>${esc(t.test_id)} · ${esc(t.title)}</h4>
        <p class="note">${esc(t.expected_behavior || "")}</p>
        <p>${esc(c.notes)}</p>
        <div class="meta note">Matched rules: ${rules.map((r) => `<code>${esc(r.team_rule_id)}</code> ${esc(r.citation)}`).join("; ") || "none"}</div>
        <div class="counts"><strong>${c.affected_address_ids.length} affected</strong>${byState(c.affected_address_ids)}</div>
        ${c.conflict_flag_address_ids.length ? `<div class="counts"><strong>${c.conflict_flag_address_ids.length} flagged for conflict</strong>${byState(c.conflict_flag_address_ids)}</div>` : ""}
      </article>`;
  }).join("");
}

function renderMethod(method) {
  $("#method").innerHTML = method.html;
}

function selectAddress(id) {
  const a = state.addresses[id];
  if (!a) return;
  state.current = a;
  $("#q").value = addressLabel(a);
  history.replaceState(null, "", `#${id}`);
  renderLookup();
}

function setupTabs() {
  document.querySelectorAll(".tabs button").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".tabs button").forEach((b) => b.setAttribute("aria-selected", b === btn));
      document.querySelectorAll(".tab").forEach((t) => { t.hidden = t.id !== `tab-${btn.dataset.tab}`; });
    });
  });
}

function fillSelect(sel, values, label = (v) => v) {
  values.forEach((v) => sel.insertAdjacentHTML("beforeend", `<option value="${esc(v)}">${esc(label(v))}</option>`));
}

async function main() {
  setupTabs();
  const [rules, addresses, changes, tests, method] = await Promise.all([
    loadJSON("data/rules.json"), loadJSON("data/addresses.json"), loadJSON("data/changes.json"),
    loadJSON("data/tests.json"), loadJSON("data/method.json"),
  ]);
  state.rules = rules;
  state.byId = Object.fromEntries(rules.map((r) => [r.team_rule_id, r]));
  state.addresses = addresses;

  const options = $("#address-options");
  for (const a of Object.values(addresses)) {
    const label = addressLabel(a);
    state.labelToId[label] = a.address_id;
    options.insertAdjacentHTML("beforeend", `<option value="${esc(label)}"></option>`);
  }
  $("#examples").innerHTML = EXAMPLES.filter((id) => addresses[id])
    .map((id) => `<button type="button" data-addr="${id}">${esc(addresses[id].street)}, ${esc(addresses[id].postal_city)}</button>`).join(" ");

  $("#q").addEventListener("change", (e) => {
    const v = e.target.value.trim();
    const id = state.labelToId[v] || (v.toUpperCase().match(/A\d{4}/) || [])[0];
    if (id) selectAddress(id);
  });
  $("#search").addEventListener("submit", (e) => e.preventDefault());
  $("#asof").addEventListener("change", renderLookup);
  document.querySelector(".quick").addEventListener("click", (e) => {
    const t = e.target.closest("button");
    if (!t) return;
    if (t.dataset.addr) selectAddress(t.dataset.addr);
    if (t.dataset.date) { $("#asof").value = t.dataset.date; renderLookup(); }
  });

  fillSelect($("#f-juris"), [...new Set(rules.map((r) => r.jurisdiction))]);
  fillSelect($("#f-cat"), Object.keys(CATEGORY_LABELS), (c) => CATEGORY_LABELS[c]);
  fillSelect($("#f-status"), ["in_force", "not_yet_effective", "pending", "failed"], (s) => RESULT_LABELS[s]);
  ["#f-juris", "#f-cat", "#f-status"].forEach((s) => $(s).addEventListener("change", renderRules));
  renderRules();
  renderChanges(changes, tests);
  renderMethod(method);

  const start = location.hash.slice(1);
  selectAddress(addresses[start] ? start : EXAMPLES[0]);
}

main().catch((err) => {
  $("#result").innerHTML = `<p class="card">Could not load data: ${esc(err.message)}</p>`;
});
