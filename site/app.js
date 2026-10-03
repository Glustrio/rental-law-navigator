import { lookup, parseDate } from "./engine.js";

const T = {
  en: {
    disclaimer: "<strong>Not legal advice.</strong> This prototype summarizes public law text for research. Check the cited source, and talk to a lawyer or your local housing agency before acting.",
    kicker: "Rental Housing Law Navigator · CA · NJ · MA",
    title: "What the law says about this address",
    subtitle: "Which rules cover an apartment on a given date, and what is about to change. Every answer cites the law it comes from.",
    tab_lookup: "Address lookup", tab_changes: "What's changing", tab_rules: "All rules", tab_method: "How it works",
    address_label: "Any address in California, New Jersey or Massachusetts",
    address_placeholder: "e.g. 1031 Clinton St, Hoboken, NJ  or pick one of the 500 sample buildings",
    look_up: "Look up", as_of: "As of",
    search_hint: "Sample buildings come with assessor records. Other addresses are located live with the U.S. Census Geocoder; add what you know about the building below.",
    try: "Try:", dates: "Dates:",
    searching: "Looking up the address with the U.S. Census Geocoder…",
    not_found: "The Census Geocoder could not find that address. Check the spelling and include the city and state.",
    out_of_scope: (st) => `That address is in ${st}. This prototype covers California, New Jersey and Massachusetts only.`,
    address: "Address", jurisdictions: "Jurisdictions that make the rules here", building: "What we know about the building",
    built: "Year built", units: "Units", not_recorded: "not recorded", inferred: "inferred",
    edit_facts: "Know more about this building? Fill it in and the answers update.",
    apply: "Update answers", reset: "Back to the records", from_you: "entered by you",
    located_by: (m) => `Located by ${m}.`,
    no_city_rules: (c) => `We have no city-level rules for ${c} in our data, so only state rules are shown. That does not mean the city has none.`,
    answer_as_of: (d) => `Answer as of <strong>${d}</strong>. Owner type is never in the data, so rules that turn on it say "unknown".`,
    means_title: "What this means for you",
    means_applies: "These protections cover this building:",
    means_unknown: "These might apply. Here is what would settle it:",
    means_future: "Coming up or proposed (not law yet):",
    means_none: "No rule in our data reaches this building yet.",
    no_rule_cat: "No rule in this category reaches this address in our extracted law.",
    source_details: "Source text, coverage and reasoning", source: "Source", covers: "Covers", exemptions: "Exemptions",
    precedence: "Precedence", why: "Why this answer", settle: "What would settle it",
    secondary: "secondary source, official text not in corpus",
    review: "Needs human review.", review_secondary: "The official text is not in the corpus; this rule comes from a secondary source.",
    review_low: "The extraction is low-confidence.", conflict: "Flagged for human review.",
    confidence: "Confidence", effective: "Effective", key_value: "Key value", rule_id: "Rule id",
    retrieved: "retrieved",
    changes_lede: "Change tests from the challenge, run against all 500 sample addresses. Pick a test to map the addresses it affects. Each test is also checked automatically against the behavior the brief expects.",
    affected: "affected", flagged: "flagged for conflict", matched: "Matched rules", show_map: "Show on map",
    check_pass: "Self-check passed", check_fail: "Self-check failed",
    map_caption: (t, n, f) => `${t}: ${n} affected addresses (dark)${f ? `, ${f} flagged for conflict (red)` : ""}.`,
    all_juris: "All jurisdictions", all_cats: "All categories", any_status: "Any status",
    rules_count: (n, m) => `${n} of ${m} rules extracted from the corpus.`,
    footer: "Built for the RealPage × Hack-Nation challenge. Public data only. Not legal advice.",
  },
  es: {
    disclaimer: "<strong>No es asesoría legal.</strong> Este prototipo resume leyes públicas con fines de investigación. Revise la fuente citada y consulte a un abogado o a la agencia de vivienda local antes de actuar.",
    kicker: "Navegador de Leyes de Vivienda en Alquiler · CA · NJ · MA",
    title: "Lo que dice la ley sobre esta dirección",
    subtitle: "Qué reglas cubren un apartamento en una fecha dada y qué está por cambiar. Cada respuesta cita la ley de donde viene.",
    tab_lookup: "Buscar dirección", tab_changes: "Qué está cambiando", tab_rules: "Todas las reglas", tab_method: "Cómo funciona",
    address_label: "Cualquier dirección en California, Nueva Jersey o Massachusetts",
    address_placeholder: "p. ej. 1031 Clinton St, Hoboken, NJ  o elija uno de los 500 edificios de muestra",
    look_up: "Buscar", as_of: "Fecha",
    search_hint: "Los edificios de muestra traen datos del tasador. Otras direcciones se ubican en vivo con el Geocodificador del Censo de EE. UU.; agregue abajo lo que sepa del edificio.",
    try: "Pruebe:", dates: "Fechas:",
    searching: "Buscando la dirección con el Geocodificador del Censo…",
    not_found: "El Geocodificador del Censo no encontró esa dirección. Revise la ortografía e incluya ciudad y estado.",
    out_of_scope: (st) => `Esa dirección está en ${st}. Este prototipo solo cubre California, Nueva Jersey y Massachusetts.`,
    address: "Dirección", jurisdictions: "Jurisdicciones que hacen las reglas aquí", building: "Lo que sabemos del edificio",
    built: "Año de construcción", units: "Unidades", not_recorded: "sin dato", inferred: "inferido",
    edit_facts: "¿Sabe más sobre este edificio? Complételo y las respuestas se actualizan.",
    apply: "Actualizar respuestas", reset: "Volver a los registros", from_you: "dato ingresado por usted",
    located_by: (m) => `Ubicado con ${m}.`,
    no_city_rules: (c) => `No tenemos reglas municipales de ${c} en nuestros datos; solo se muestran reglas estatales. Eso no significa que la ciudad no tenga.`,
    answer_as_of: (d) => `Respuesta a la fecha <strong>${d}</strong>. El tipo de propietario nunca está en los datos, así que las reglas que dependen de eso dicen "desconocido".`,
    means_title: "Qué significa para usted",
    means_applies: "Estas protecciones cubren este edificio:",
    means_unknown: "Estas podrían aplicar. Esto lo aclararía:",
    means_future: "Próximas o propuestas (todavía no son ley):",
    means_none: "Ninguna regla de nuestros datos alcanza este edificio todavía.",
    no_rule_cat: "Ninguna regla de esta categoría alcanza esta dirección en la ley extraída.",
    source_details: "Texto fuente, cobertura y razonamiento", source: "Fuente", covers: "Cubre", exemptions: "Excepciones",
    precedence: "Prioridad", why: "Por qué esta respuesta (detalle técnico en inglés)", settle: "Qué lo aclararía",
    secondary: "fuente secundaria, el texto oficial no está en el corpus",
    review: "Requiere revisión humana.", review_secondary: "El texto oficial no está en el corpus; esta regla viene de una fuente secundaria.",
    review_low: "La extracción tiene baja confianza.", conflict: "Marcado para revisión humana.",
    confidence: "Confianza", effective: "Vigente desde", key_value: "Valor clave", rule_id: "Id de regla",
    retrieved: "consultado",
    changes_lede: "Pruebas de cambio del reto, aplicadas a las 500 direcciones de muestra. Elija una prueba para ver en el mapa las direcciones afectadas. Cada prueba también se verifica automáticamente contra el comportamiento esperado.",
    affected: "afectadas", flagged: "marcadas por conflicto", matched: "Reglas asociadas", show_map: "Ver en el mapa",
    check_pass: "Autoverificación aprobada", check_fail: "Autoverificación fallida",
    map_caption: (t, n, f) => `${t}: ${n} direcciones afectadas (oscuro)${f ? `, ${f} marcadas por conflicto (rojo)` : ""}.`,
    all_juris: "Todas las jurisdicciones", all_cats: "Todas las categorías", any_status: "Cualquier estado",
    rules_count: (n, m) => `${n} de ${m} reglas extraídas del corpus.`,
    footer: "Hecho para el reto RealPage × Hack-Nation. Solo datos públicos. No es asesoría legal.",
  },
};

const CATEGORY = {
  en: {
    rent_increase_limits: "Rent increases", just_cause_eviction: "Just-cause eviction", security_deposits: "Security deposits",
    application_screening_fees: "Application and screening fees", screening_restrictions: "Screening restrictions",
    algorithmic_rent_setting: "Algorithmic rent-setting",
  },
  es: {
    rent_increase_limits: "Aumentos de renta", just_cause_eviction: "Desalojo con causa justa", security_deposits: "Depósitos de garantía",
    application_screening_fees: "Cargos de solicitud y evaluación", screening_restrictions: "Límites a la evaluación de inquilinos",
    algorithmic_rent_setting: "Rentas fijadas por algoritmos",
  },
};

const RESULT = {
  en: { applies: "Applies", unknown: "Unknown", superseded: "Superseded", not_yet_effective: "Not yet effective", pending: "Pending bill", failed: "Failed", in_force: "In force" },
  es: { applies: "Aplica", unknown: "Desconocido", superseded: "Desplazada", not_yet_effective: "Aún no vigente", pending: "Proyecto pendiente", failed: "Fracasó", in_force: "Vigente" },
};

const LEAD_ES = {
  applies: "Esta regla cubre este edificio.",
  unknown: "Esta regla podría cubrir este edificio, pero los datos no alcanzan para decidir.",
  superseded: "Aquí la desplaza una regla local más estricta.",
  not_yet_effective: "Fue aprobada pero todavía no está vigente.",
  pending: "Es una propuesta pendiente, no es ley.",
};

const STATE_NAMES = { CA: "California", NJ: "New Jersey", MA: "Massachusetts" };
const EXAMPLES = ["A0002", "A0001", "A0009", "A0005"];
const LIVE_EXAMPLE = "1500 Ocean Ave, Santa Monica, CA";

const $ = (sel) => document.querySelector(sel);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

const state = {
  lang: "en", rules: [], byId: {}, addresses: {}, plain: {}, changes: {}, tests: [], method: { html: "" },
  labelToId: {}, base: null, overrides: {}, map: null, mapLayer: null, mapTest: null,
};

const t = (key, ...args) => {
  const v = T[state.lang][key] ?? T.en[key];
  return typeof v === "function" ? v(...args) : v;
};

function ruleText(rule, field) {
  const p = state.plain[rule.team_rule_id] || {};
  if (state.lang === "es") {
    const es = { title: p.title_es, requirement: p.requirement_es, key_value: p.key_value_es, summary: p.summary_es, settle: p.settle_hint_es }[field];
    if (es) return es;
  }
  return { title: rule.title, requirement: rule.requirement, key_value: rule.key_value, summary: p.summary_en, settle: p.settle_hint_en }[field];
}

async function loadJSON(path) {
  const res = await fetch(path);
  if (!res.ok) throw new Error(`${path}: ${res.status}`);
  return res.json();
}

function applyI18n() {
  document.documentElement.lang = state.lang;
  document.querySelectorAll("[data-i18n]").forEach((el) => { el.textContent = t(el.dataset.i18n); });
  document.querySelectorAll("[data-i18n-html]").forEach((el) => { el.innerHTML = t(el.dataset.i18nHtml); });
  document.querySelectorAll("[data-i18n-placeholder]").forEach((el) => { el.placeholder = t(el.dataset.i18nPlaceholder); });
  document.querySelectorAll(".lang button").forEach((b) => b.setAttribute("aria-pressed", b.dataset.lang === state.lang));
}

// ---------- addresses ----------

function addressLabel(a) {
  return `${a.street}, ${a.postal_city}, ${a.state} (${a.address_id})`;
}

function coveredCities() {
  return new Set(state.rules.filter((r) => r.level === "city").map((r) => r.jurisdiction));
}

function effectiveAddress() {
  const a = { ...state.base };
  const o = state.overrides;
  if (o.year_built != null) a.year_built = o.year_built;
  if (o.units != null) {
    a.units_low = o.units;
    a.units_high = o.units;
    a.units_note = "unit count entered by you";
  }
  return a;
}

function geocodeLive(text) {
  return new Promise((resolve, reject) => {
    const cb = `census_cb_${Date.now()}`;
    const params = new URLSearchParams({
      address: text, benchmark: "Public_AR_Current", vintage: "Current_Current",
      layers: "Incorporated Places,Counties,States", format: "jsonp", callback: cb,
    });
    const script = document.createElement("script");
    const timer = setTimeout(() => { cleanup(); reject(new Error("timeout")); }, 20000);
    function cleanup() { clearTimeout(timer); delete window[cb]; script.remove(); }
    window[cb] = (data) => { cleanup(); resolve(data); };
    script.onerror = () => { cleanup(); reject(new Error("network")); };
    script.src = `https://geocoding.geo.census.gov/geocoder/geographies/onelineaddress?${params}`;
    document.body.appendChild(script);
  });
}

async function lookUpLive(text) {
  const status = $("#search-status");
  status.textContent = t("searching");
  let data;
  try {
    data = await geocodeLive(text);
  } catch {
    status.textContent = t("not_found");
    return;
  }
  const m = data?.result?.addressMatches?.[0];
  if (!m) { status.textContent = t("not_found"); return; }
  const g = m.geographies || {};
  const st = g.States?.[0]?.STUSAB || m.addressComponents?.state;
  if (!STATE_NAMES[st]) { status.textContent = t("out_of_scope", st || "?"); return; }
  const place = g["Incorporated Places"]?.[0];
  const city = place ? place.BASENAME : null;
  const notes = [];
  if (!city) notes.push("no incorporated city at this point; only state rules are tested");
  const parts = m.matchedAddress.split(",").map((s) => s.trim());
  const a = {
    address_id: "LIVE", street: parts[0], postal_city: parts[1] || "", state: st, zip: m.addressComponents?.zip || "",
    year_built: null, units_low: null, units_high: null, units_note: "unit count not recorded", use_description: "",
    city, county: g.Counties?.[0]?.NAME || null, geocode_method: "census", lon: m.coordinates.x, lat: m.coordinates.y, notes,
  };
  a.jurisdictions = city ? [st, `${city}, ${st}`] : [st];
  status.textContent = t("search_hint");
  state.base = a;
  state.overrides = {};
  history.replaceState(null, "", `#live=${encodeURIComponent(text)}`);
  renderLookup();
}

function selectSample(id) {
  const a = state.addresses[id];
  if (!a) return;
  state.base = a;
  state.overrides = {};
  $("#q").value = addressLabel(a);
  history.replaceState(null, "", `#${id}`);
  renderLookup();
}

// ---------- lookup view ----------

function badge(result) {
  return `<span class="badge ${result}">${RESULT[state.lang][result] || result}</span>`;
}

function unitsText(a) {
  if (a.units_low == null) return `<em>${t("not_recorded")}</em>`;
  if (a.units_low === a.units_high) return String(a.units_low);
  return `${a.units_low}${a.units_high ? `–${a.units_high}` : "+"} (${t("inferred")})`;
}

function factsForm(a) {
  const o = state.overrides;
  return `
    <form class="facts" id="facts">
      <p class="note">${t("edit_facts")}</p>
      <div class="facts-row">
        <label class="field"><span>${t("built")}</span>
          <input name="year_built" type="number" min="1800" max="2030" placeholder="${a.year_built ?? ""}" value="${o.year_built ?? ""}"></label>
        <label class="field"><span>${t("units")}</span>
          <input name="units" type="number" min="1" max="2000" placeholder="${a.units_low === a.units_high && a.units_low != null ? a.units_low : ""}" value="${o.units ?? ""}"></label>
        <button type="submit" class="primary">${t("apply")}</button>
        ${Object.keys(o).length ? `<button type="button" id="reset-facts">${t("reset")}</button>` : ""}
      </div>
    </form>`;
}

function meansForYou(results) {
  const pick = (res) => results.filter((r) => res.includes(r.result)).map((r) => [r, state.byId[r.team_rule_id]]);
  const applies = pick(["applies"]);
  const unknown = pick(["unknown"]);
  const future = pick(["not_yet_effective", "pending"]);
  const line = ([r, rule], withHint) => {
    const summary = ruleText(rule, "summary") || ruleText(rule, "requirement");
    const hint = withHint && ruleText(rule, "settle") ? `<div class="note">${t("settle")}: ${esc(ruleText(rule, "settle"))}</div>` : "";
    return `<li><strong>${esc(CATEGORY[state.lang][rule.category])}.</strong> ${esc(summary)} <span class="cite">${esc(rule.citation)}</span>${hint}</li>`;
  };
  if (!applies.length && !unknown.length && !future.length) return `<div class="card means"><h2>${t("means_title")}</h2><p>${t("means_none")}</p></div>`;
  return `
    <div class="card means">
      <h2>${t("means_title")}</h2>
      ${applies.length ? `<p>${t("means_applies")}</p><ul>${applies.map((x) => line(x, false)).join("")}</ul>` : ""}
      ${unknown.length ? `<p>${t("means_unknown")}</p><ul>${unknown.map((x) => line(x, true)).join("")}</ul>` : ""}
      ${future.length ? `<p>${t("means_future")}</p><ul>${future.map((x) => line(x, false)).join("")}</ul>` : ""}
    </div>`;
}

function renderLookup() {
  const out = $("#result");
  if (!state.base) return;
  const a = effectiveAddress();
  const asOfValue = $("#asof").value || "2026-10-01";
  const results = lookup(a, state.rules, parseDate(asOfValue));
  const crumbs = a.jurisdictions.map((j) => (j.length === 2 ? STATE_NAMES[j] : j.split(",")[0]));
  const cityKey = a.city ? `${a.city}, ${a.state}` : null;
  const counts = {};
  results.forEach((r) => { counts[r.result] = (counts[r.result] || 0) + 1; });

  let html = `
    <div class="card stack">
      <div>
        <div class="label">${t("address")}</div>
        <h2>${esc(a.street)}</h2>
        <div>${esc(a.postal_city)}, ${esc(a.state)} ${esc(a.zip)}</div>
      </div>
      <div>
        <div class="label">${t("jurisdictions")}</div>
        <div class="crumbs">${crumbs.map(esc).join(" › ")}</div>
        ${a.county ? `<div class="note">${esc(a.county)}</div>` : ""}
        <div class="note">${t("located_by", a.geocode_method === "census" ? "U.S. Census Geocoder" : esc(a.geocode_method.replaceAll("_", " ")))}</div>
        ${a.notes.map((n) => `<div class="note">${esc(n)}.</div>`).join("")}
        ${cityKey && !coveredCities().has(cityKey) ? `<div class="flagbox">${t("no_city_rules", esc(a.city))}</div>` : ""}
      </div>
      <div>
        <div class="label">${t("building")}</div>
        <div>${t("built")}: ${a.year_built ?? `<em>${t("not_recorded")}</em>`}</div>
        <div>${t("units")}: ${unitsText(a)}</div>
        <div class="note">${esc(a.units_note)}${a.use_description ? `. ${esc(a.use_description)}` : ""}</div>
      </div>
    </div>
    ${factsForm(state.base)}
    <p class="asof">${t("answer_as_of", esc(asOfValue))}</p>
    <div class="summary-bar">${Object.entries(counts).map(([k, n]) => `${badge(k)} <span class="note">${n}</span>`).join(" ")}</div>
    ${meansForYou(results)}`;

  const byCat = {};
  results.forEach((r) => {
    const rule = state.byId[r.team_rule_id];
    (byCat[rule.category] ||= []).push([r, rule]);
  });
  Object.keys(CATEGORY.en).forEach((cat, i) => {
    html += `<h3 class="cat"><span class="sec">§ ${i + 1}</span>${CATEGORY[state.lang][cat]}</h3>`;
    const items = byCat[cat] || [];
    html += items.length ? items.map(([r, rule]) => ruleCard(rule, r)).join("") : `<div class="card note">${t("no_rule_cat")}</div>`;
  });
  out.innerHTML = html;

  $("#facts").addEventListener("submit", (e) => {
    e.preventDefault();
    const f = new FormData(e.target);
    const num = (v) => (v === "" || v == null ? null : Number(v));
    state.overrides = {};
    if (num(f.get("year_built")) != null) state.overrides.year_built = num(f.get("year_built"));
    if (num(f.get("units")) != null) state.overrides.units = num(f.get("units"));
    renderLookup();
  });
  $("#reset-facts")?.addEventListener("click", () => { state.overrides = {}; renderLookup(); });
}

function sourceLine(rule) {
  const secondary = rule.source_origin === "supplement" || /secondary/.test(rule.source_type) ? ` · ${t("secondary")}` : "";
  return `<a href="${esc(rule.source_url)}" target="_blank" rel="noopener">${esc(rule.source_doc_id)}</a>, ${t("retrieved")} ${esc(rule.retrieved_at)}${secondary}`;
}

function ruleCard(rule, r) {
  const summary = ruleText(rule, "summary");
  const lead = r && state.lang === "es" ? LEAD_ES[r.result] : null;
  const settle = r && r.result === "unknown" && ruleText(rule, "settle")
    ? `<p class="settle"><strong>${t("settle")}:</strong> ${esc(ruleText(rule, "settle"))}</p>` : "";
  const flags = [
    r && r.conflict_flag ? `<div class="flagbox"><strong>${t("conflict")}</strong> ${esc(rule.conflict_note)}</div>` : "",
    r && r.needs_review ? `<div class="flagbox"><strong>${t("review")}</strong> ${rule.source_origin === "supplement" ? t("review_secondary") : t("review_low")}</div>` : "",
  ].join("");
  return `
    <article class="rule">
      <div class="margin">
        ${r ? badge(r.result) : badge(rule.status)}
        ${r && r.conflict_flag ? `<span class="badge flag">${state.lang === "es" ? "Conflicto" : "Conflict"}</span>` : ""}
        <span class="conf">${t("confidence")} <b>${Math.round((r ? r.confidence : rule.confidence ?? 0) * 100)}%</b></span>
      </div>
      <div class="body">
      <h4>${esc(ruleText(rule, "title"))}</h4>
      ${summary ? `<p class="summary">${esc(summary)}</p>` : ""}
      <p class="req">${esc(ruleText(rule, "requirement"))}</p>
      ${r ? `<p class="why">${esc(lead || r.explanation)}</p>` : ""}
      ${settle}
      <div class="meta">
        <span><code>${esc(rule.citation)}</code></span>
        <span>${esc(rule.jurisdiction)} · ${rule.level}</span>
        ${rule.effective_date ? `<span>${t("effective")} ${esc(rule.effective_date)}</span>` : ""}
        ${ruleText(rule, "key_value") ? `<span>${t("key_value")}: ${esc(ruleText(rule, "key_value"))}</span>` : ""}
      </div>
      ${flags}
      <details>
        <summary>${t("source_details")}</summary>
        <blockquote>${esc(rule.quoted_span)}</blockquote>
        <div class="note">${t("source")}: ${sourceLine(rule)}</div>
        ${r ? `<p><strong>${t("why")}:</strong> ${esc(r.reasons.join("; ") || r.explanation)}</p>` : ""}
        <p><strong>${t("covers")}:</strong> ${esc(rule.coverage_conditions)}</p>
        ${rule.exemptions ? `<p><strong>${t("exemptions")}:</strong> ${esc(rule.exemptions)}</p>` : ""}
        ${rule.interaction ? `<p><strong>${t("precedence")}:</strong> ${esc(rule.interaction)}</p>` : ""}
        <p class="note">${t("rule_id")} ${esc(rule.team_rule_id)}${rule.also_supported_by?.length ? ` · ${rule.also_supported_by.map(esc).join(", ")}` : ""}</p>
      </details>
      </div>
    </article>`;
}

// ---------- rules tab ----------

function fillFilters() {
  const opts = (values, label) => values.map((v) => `<option value="${esc(v)}">${esc(label(v))}</option>`).join("");
  const keep = ["#f-juris", "#f-cat", "#f-status"].map((s) => $(s).value);
  $("#f-juris").innerHTML = `<option value="">${t("all_juris")}</option>` + opts([...new Set(state.rules.map((r) => r.jurisdiction))], (v) => v);
  $("#f-cat").innerHTML = `<option value="">${t("all_cats")}</option>` + opts(Object.keys(CATEGORY.en), (c) => CATEGORY[state.lang][c]);
  $("#f-status").innerHTML = `<option value="">${t("any_status")}</option>` + opts(["in_force", "not_yet_effective", "pending", "failed"], (s) => RESULT[state.lang][s]);
  ["#f-juris", "#f-cat", "#f-status"].forEach((s, i) => { $(s).value = keep[i]; });
}

function renderRules() {
  const j = $("#f-juris").value, c = $("#f-cat").value, s = $("#f-status").value;
  const list = state.rules.filter((r) => (!j || r.jurisdiction === j) && (!c || r.category === c) && (!s || r.status === s));
  $("#rules").innerHTML = `<p class="note">${t("rules_count", list.length, state.rules.length)}</p>` + list.map((r) => ruleCard(r, null)).join("");
}

// ---------- changes tab ----------

function tally(ids) {
  const counts = {};
  ids.forEach((id) => {
    const a = state.addresses[id];
    const key = a.city ? `${a.city}, ${a.state}` : a.state;
    counts[key] = (counts[key] || 0) + 1;
  });
  return Object.entries(counts).map(([k, n]) => `<span>${esc(k)}: ${n}</span>`).join("");
}

function renderChanges() {
  $("#changes").innerHTML = state.tests.map((test) => {
    const c = state.changes[test.test_id] || { affected_address_ids: [], conflict_flag_address_ids: [], our_rule_ids: [], notes: "" };
    const rules = c.our_rule_ids.map((id) => state.byId[id]).filter(Boolean);
    const check = c.self_check;
    return `
      <article class="card test ${state.mapTest === test.test_id ? "active" : ""}">
        <div class="rule-head">
          <h4>${esc(test.test_id)} · ${esc(test.title)}</h4>
          ${check ? `<span class="badge ${check.passed ? "applies" : "pending"}">${check.passed ? t("check_pass") : t("check_fail")}</span>` : ""}
        </div>
        <p class="note">${esc(test.expected_behavior || "")}</p>
        <p>${esc(c.notes)}</p>
        ${check ? `<p class="note">${esc(check.detail)}</p>` : ""}
        <div class="meta note">${t("matched")}: ${rules.map((r) => `<code>${esc(r.team_rule_id)}</code> ${esc(r.citation)}`).join("; ") || "—"}</div>
        <div class="counts"><strong>${c.affected_address_ids.length} ${t("affected")}</strong>${tally(c.affected_address_ids)}</div>
        ${c.conflict_flag_address_ids.length ? `<div class="counts"><strong>${c.conflict_flag_address_ids.length} ${t("flagged")}</strong>${tally(c.conflict_flag_address_ids)}</div>` : ""}
        ${c.affected_address_ids.length ? `<button type="button" class="map-btn" data-test="${esc(test.test_id)}">${t("show_map")}</button>` : ""}
      </article>`;
  }).join("");
  document.querySelectorAll(".map-btn").forEach((b) => b.addEventListener("click", () => showOnMap(b.dataset.test)));
}

function showOnMap(testId) {
  if (!window.L) return;
  if (!state.map) {
    state.map = L.map("map", { scrollWheelZoom: false });
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 18, attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    }).addTo(state.map);
  }
  state.mapTest = testId;
  state.mapLayer?.remove();
  const c = state.changes[testId];
  const flagged = new Set(c.conflict_flag_address_ids);
  const markers = c.affected_address_ids.map((id) => state.addresses[id]).filter((a) => a.lat != null).map((a) =>
    L.circleMarker([a.lat, a.lon], {
      radius: 5, weight: 1.5, color: flagged.has(a.address_id) ? "#5e1f12" : "#1b1f24",
      fillColor: flagged.has(a.address_id) ? "#b8432a" : "#2f4f6f", fillOpacity: 0.85,
    }).bindPopup(`${esc(a.street)}, ${esc(a.postal_city)}<br><a href="#${a.address_id}">${a.address_id}</a>`));
  state.mapLayer = L.featureGroup(markers).addTo(state.map);
  if (markers.length) state.map.fitBounds(state.mapLayer.getBounds(), { padding: [20, 20] });
  const test = state.tests.find((x) => x.test_id === testId);
  $("#map-caption").textContent = t("map_caption", `${testId} · ${test.title}`, c.affected_address_ids.length, c.conflict_flag_address_ids.length);
  renderChanges();
  setTimeout(() => state.map.invalidateSize(), 50);
}

// ---------- shell ----------

function renderAll() {
  applyI18n();
  fillFilters();
  renderRules();
  renderChanges();
  $("#method").innerHTML = state.method.html;
  $("#examples").innerHTML = EXAMPLES.filter((id) => state.addresses[id])
    .map((id) => `<button type="button" data-addr="${id}">${esc(state.addresses[id].street)}, ${esc(state.addresses[id].postal_city)}</button>`).join(" ")
    + ` <button type="button" data-live="${esc(LIVE_EXAMPLE)}">${esc(LIVE_EXAMPLE)}</button>`;
  renderLookup();
}

function setupTabs() {
  document.querySelectorAll(".tabs button").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".tabs button").forEach((b) => b.setAttribute("aria-selected", b === btn));
      document.querySelectorAll(".tab").forEach((tab) => { tab.hidden = tab.id !== `tab-${btn.dataset.tab}`; });
      if (btn.dataset.tab === "changes" && !state.mapTest) {
        const first = state.tests.find((x) => state.changes[x.test_id]?.conflict_flag_address_ids?.length) || state.tests[0];
        if (first) showOnMap(first.test_id);
      } else if (btn.dataset.tab === "changes") {
        setTimeout(() => state.map?.invalidateSize(), 50);
      }
    });
  });
}

function submitSearch() {
  const v = $("#q").value.trim();
  if (!v) return;
  const id = state.labelToId[v] || (v.toUpperCase().match(/^A\d{4}$/) || [])[0];
  if (id && state.addresses[id]) selectSample(id);
  else lookUpLive(v);
}

async function main() {
  setupTabs();
  const [rules, addresses, changes, tests, method, plain] = await Promise.all([
    loadJSON("data/rules.json"), loadJSON("data/addresses.json"), loadJSON("data/changes.json"),
    loadJSON("data/tests.json"), loadJSON("data/method.json"), loadJSON("data/plain.json"),
  ]);
  Object.assign(state, { rules, addresses, changes, tests, method, plain });
  state.byId = Object.fromEntries(rules.map((r) => [r.team_rule_id, r]));

  const options = $("#address-options");
  for (const a of Object.values(addresses)) {
    const label = addressLabel(a);
    state.labelToId[label] = a.address_id;
    options.insertAdjacentHTML("beforeend", `<option value="${esc(label)}"></option>`);
  }

  $("#search").addEventListener("submit", (e) => { e.preventDefault(); submitSearch(); });
  $("#q").addEventListener("change", () => { if (state.labelToId[$("#q").value.trim()]) submitSearch(); });
  $("#asof").addEventListener("change", renderLookup);
  document.querySelector(".quick").addEventListener("click", (e) => {
    const b = e.target.closest("button");
    if (!b) return;
    if (b.dataset.addr) selectSample(b.dataset.addr);
    if (b.dataset.live) { $("#q").value = b.dataset.live; lookUpLive(b.dataset.live); }
    if (b.dataset.date) { $("#asof").value = b.dataset.date; renderLookup(); }
  });
  ["#f-juris", "#f-cat", "#f-status"].forEach((s) => $(s).addEventListener("change", renderRules));
  document.querySelectorAll(".lang button").forEach((b) => b.addEventListener("click", () => {
    state.lang = b.dataset.lang;
    try { localStorage.setItem("lang", state.lang); } catch { /* storage unavailable */ }
    renderAll();
  }));
  try { state.lang = localStorage.getItem("lang") || (navigator.language?.startsWith("es") ? "es" : "en"); } catch { /* ignore */ }

  const hash = decodeURIComponent(location.hash.slice(1));
  if (hash.startsWith("live=")) {
    $("#q").value = hash.slice(5);
    state.base = null;
    renderAll();
    lookUpLive(hash.slice(5));
  } else {
    state.base = addresses[hash] || addresses[EXAMPLES[0]];
    $("#q").value = addressLabel(state.base);
    renderAll();
  }
  window.addEventListener("hashchange", () => {
    const h = location.hash.slice(1);
    if (addresses[h]) {
      document.querySelector('.tabs button[data-tab="lookup"]').click();
      selectSample(h);
    }
  });
}

main().catch((err) => {
  $("#result").innerHTML = `<p class="card">Could not load data: ${esc(err.message)}</p>`;
});
