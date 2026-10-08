// build_deck.js -- renders Group10.pptx from slides/build/deck_data.json.
//
// Owner: Part 1 -- Yeo Kai Yuan (deck assembly).
//
// Every number on every slide comes from deck_data.json, which
// slides/collect_deck_data.py builds from committed files (analysis/output/,
// models/models.yaml, workload/, labelling/, docs/environment/). This file
// holds layout and wording only. Where an input is still missing, the slide
// shows an amber PENDING panel instead of a number, so a gap cannot be
// mistaken for a result; `collect_deck_data.py --final` refuses to run while
// anything is pending.
//
// Usage: node slides/build_deck.js [out.pptx]   (default: slides/Group10.pptx)

"use strict";
const fs = require("fs");
const path = require("path");
const pptxgen = require("pptxgenjs");

const REPO = path.resolve(__dirname, "..");
const D = JSON.parse(fs.readFileSync(path.join(__dirname, "build", "deck_data.json"), "utf8"));
const OUT = process.argv[2] || path.join(__dirname, "Group10.pptx");

// ---------------------------------------------------------------- palette ---
const C = {
  dark: "0E2A33", ink: "17252C", muted: "5B6B73", light: "EEF3F4", line: "C9D5D8",
  teal: "1F6F78", tealLight: "D5E8EA", amber: "E39B2D", amberLight: "FBEBD2",
  pass: "2E7D5B", passLight: "DCEFE5", fail: "B23A48", failLight: "F6DDE0", white: "FFFFFF",
};
const HEAD = "Cambria";
const BODY = "Calibri";
const W = 13.333, H = 7.5, MX = 0.55;

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE";
pres.author = "ICT3113 Group 10";
pres.title = `Group ${D.team.group}: ${D.team.title}`;
pres.subject = "ICT3113 Assignment 1 — Performance Requirements and Testing";

pres.defineSlideMaster({
  title: "CONTENT",
  background: { color: C.white },
  objects: [
    { placeholder: { options: { name: "title", type: "title", x: MX, y: 0.32, w: W - 2 * MX, h: 0.62,
      fontFace: HEAD, fontSize: 28, bold: true, color: C.ink, valign: "middle", margin: 0 }, text: "" } },
  ],
  slideNumber: { x: W - 1.05, y: H - 0.42, w: 0.6, h: 0.3, fontFace: BODY, fontSize: 9, color: C.muted, align: "right" },
});
pres.defineSlideMaster({ title: "COVER", background: { color: C.dark }, objects: [] });

// ---------------------------------------------------------------- helpers ---
const fmt = (v, digits = 0) => (v === null || v === undefined || Number.isNaN(v)) ? "–"
  : Number(v).toLocaleString("en-GB", { minimumFractionDigits: digits, maximumFractionDigits: digits });
const ms = (v) => (v === null || v === undefined) ? "–" : (v >= 10000 ? `${fmt(v / 1000, 1)} s` : `${fmt(v)} ms`);
const pct = (v, digits = 1) => (v === null || v === undefined) ? "–" : `${fmt(v * 100, digits)}%`;

function frame(title, message, source) {
  const s = pres.addSlide({ masterName: "CONTENT" });
  s.addText(title, { placeholder: "title" });
  if (message) {
    s.addText(message, { x: MX, y: 0.95, w: W - 2 * MX, h: 0.45, fontFace: BODY, fontSize: 15,
      color: C.teal, margin: 0, valign: "top", isTextBox: true });
  }
  if (source) {
    s.addText(`Source: ${source}`, { x: MX, y: H - 0.45, w: W - 2.0, h: 0.32, fontFace: BODY, fontSize: 9,
      color: C.muted, margin: 0, valign: "middle", isTextBox: true });
  }
  return s;
}

function box(s, x, y, w, h, fill, opts = {}) {
  s.addShape(pres.ShapeType.roundRect, { x, y, w, h, fill: { color: fill }, rectRadius: opts.radius ?? 0.08,
    line: opts.line ? { color: opts.line, width: opts.lineWidth ?? 1, dashType: opts.dash ?? "solid" } : { color: fill, width: 0 } });
}

function text(s, t, x, y, w, h, o = {}) {
  s.addText(t, { x, y, w, h, fontFace: o.face ?? BODY, fontSize: o.size ?? 13, color: o.color ?? C.ink,
    bold: o.bold ?? false, italic: o.italic ?? false, align: o.align ?? "left", valign: o.valign ?? "top",
    margin: o.margin ?? 0.06, paraSpaceAfter: o.para ?? 0, isTextBox: true, fit: "none",
    lineSpacingMultiple: o.lsm ?? 1.0 });
}

function pending(s, x, y, w, h, what) {
  box(s, x, y, w, h, C.amberLight, { line: C.amber, dash: "dash" });
  text(s, [{ text: "PENDING — ", options: { bold: true, color: C.amber } },
           { text: what, options: { color: C.ink } }], x + 0.15, y + 0.1, w - 0.3, h - 0.2, { size: 13, valign: "middle" });
}

function badge(s, label, x, y, kind) {
  const fill = { CITED: C.teal, ESTIMATE: C.amber, MEASURED: C.pass, ASSUMED: C.amber }[kind] ?? C.muted;
  box(s, x, y, 0.95, 0.24, fill, { radius: 0.05 });
  text(s, label, x, y, 0.95, 0.24, { size: 8.5, bold: true, color: C.white, align: "center", valign: "middle", margin: 0 });
}

function table(s, rows, x, y, w, colW, o = {}) {
  const header = rows[0].map((cell) => ({ text: cell, options: { bold: true, color: C.white, fill: { color: C.dark },
    fontSize: o.headSize ?? 11, valign: "middle" } }));
  const body = rows.slice(1).map((row, i) => row.map((cell) => {
    if (cell && typeof cell === "object" && !Array.isArray(cell)) {
      return { text: cell.text, options: { fill: { color: cell.fill ?? (i % 2 ? C.light : C.white) }, color: cell.color ?? C.ink,
        bold: cell.bold ?? false, fontSize: cell.size ?? o.size ?? 11, align: cell.align ?? "left", valign: "middle" } };
    }
    return { text: String(cell ?? ""), options: { fill: { color: i % 2 ? C.light : C.white }, color: C.ink,
      fontSize: o.size ?? 11, valign: "middle" } };
  }));
  s.addTable([header, ...body], { x, y, w, colW, fontFace: BODY, border: { type: "solid", pt: 0.5, color: C.line },
    margin: o.margin ?? [3, 5, 3, 5], rowH: o.rowH, autoPage: false });
}

const passCell = (ok, label) => ok === null || ok === undefined
  ? { text: label ?? "pending", fill: C.amberLight, color: C.amber, bold: true, align: "center" }
  : { text: label ?? (ok ? "meets" : "fails"), fill: ok ? C.passLight : C.failLight, color: ok ? C.pass : C.fail, bold: true, align: "center" };

const MODEL_ORDER = D.models.map((m) => m.tag);
const shortDigest = (d) => d ? d.replace(/^sha256:/, "").slice(0, 12) : null;

// =========================================================== SLIDE 1 cover ===
(() => {
  const s = pres.addSlide({ masterName: "COVER" });
  text(s, D.team.course, MX, 0.45, 9, 0.35, { size: 13, color: "9FB7BE" });
  box(s, W - MX - 1.6, 0.42, 1.6, 0.42, C.amber, { radius: 0.06 });
  text(s, `Group ${D.team.group}`, W - MX - 1.6, 0.42, 1.6, 0.42, { size: 16, bold: true, color: C.dark, align: "center", valign: "middle", margin: 0 });
  text(s, D.team.title, MX, 1.25, 12.2, 0.95, { face: HEAD, size: 40, bold: true, color: C.white, valign: "middle", margin: 0 });
  text(s, D.team.subtitle, MX, 2.2, 11.5, 0.5, { size: 18, color: C.amber, margin: 0 });

  const rows = [["Member", "Student ID", "Role"]].concat(D.team.members.map((m) => [
    m.name, m.student_id ? m.student_id : { text: "ID pending", color: C.amber, bold: true }, m.role]));
  const header = rows[0].map((t) => ({ text: t, options: { bold: true, color: C.dark, fill: { color: "9FB7BE" }, fontSize: 12 } }));
  const body = rows.slice(1).map((r) => r.map((c) => typeof c === "object"
    ? { text: c.text, options: { color: c.color, bold: c.bold, fill: { color: "163B46" }, fontSize: 13 } }
    : { text: c, options: { color: C.white, fill: { color: "163B46" }, fontSize: 13 } }));
  s.addTable([header, ...body], { x: MX, y: 3.05, w: 8.4, colW: [2.6, 1.5, 4.3], fontFace: BODY,
    border: { type: "solid", pt: 0.5, color: "2D5562" }, margin: [4, 6, 4, 6], autoPage: false });

  box(s, 9.35, 3.05, 3.43, 2.42, "163B46", { line: "2D5562" });
  text(s, "Repository", 9.5, 3.15, 3.1, 0.3, { size: 12, bold: true, color: "9FB7BE" });
  s.addText(D.team.repository.replace("https://", ""), { x: 9.5, y: 3.45, w: 3.2, h: 0.5, fontFace: BODY, fontSize: 13,
    color: C.amber, hyperlink: { url: D.team.repository }, margin: 0.06, isTextBox: true });
  text(s, [{ text: "Rebuild and run the service:", options: { breakLine: true, color: "9FB7BE" } },
           { text: "git clone <repository>", options: { breakLine: true, fontFace: "Courier New", color: C.white } },
           { text: "docker compose --profile local-ollama up -d --build", options: { fontFace: "Courier New", color: C.white } }],
       9.5, 4.0, 3.2, 1.35, { size: 10.5 });

  const cats = D.architecture.categories;
  const cw = (W - 2 * MX - 0.12 * (cats.length - 1)) / cats.length;
  cats.forEach((c, i) => {
    box(s, MX + i * (cw + 0.12), 6.15, cw, 0.5, i % 2 ? "1A4A55" : "235C68", { radius: 0.1 });
    text(s, c, MX + i * (cw + 0.12), 6.15, cw, 0.5, { size: 10.5, color: C.white, align: "center", valign: "middle", margin: 0.02 });
  });
  text(s, "The seven routing categories the service assigns — every ticket from team rows 10000–10999 of the CFPB-derived course extract",
       MX, 6.72, 12.2, 0.3, { size: 10, color: "9FB7BE", margin: 0 });
})();

// ===================================================== SLIDE 2 architecture ===
(() => {
  const a = D.architecture;
  const s = frame("Service architecture",
    "A synchronous FastAPI service in Docker calls one CPU-only Ollama model per ticket; JMeter plays the complaint intake from a separate machine.",
    "service/main.py, docker-compose.yml, .env.example, service/log_schema.py (A2 candidate comments mark each deliberate non-optimisation)");
  // load generator
  box(s, MX, 1.75, 2.75, 3.05, C.light, { line: C.line });
  text(s, "LOAD GENERATOR", MX + 0.1, 1.82, 2.5, 0.3, { size: 10, bold: true, color: C.teal });
  text(s, [{ text: "MacBook, Apple M3 Pro", options: { bold: true, breakLine: true } },
           { text: "Apache JMeter 5.6.3", options: { breakLine: true } },
           { text: "Open Model Thread Group — open loop, Poisson arrivals", options: { breakLine: true } },
           { text: "Reads team rows 10000–10999 → POST /tickets", options: { breakLine: true } },
           { text: "scripts/run_accuracy.py posts the golden set" }],
       MX + 0.1, 2.12, 2.55, 2.6, { size: 11.5, para: 4 });
  // arrow + boundary
  s.addShape(pres.ShapeType.line, { x: MX + 2.8, y: 3.25, w: 1.0, h: 0, line: { color: C.teal, width: 2, endArrowType: "triangle" } });
  text(s, "HTTP over the network", MX + 2.75, 2.9, 1.15, 0.35, { size: 9, color: C.muted, align: "center" });
  // service host
  box(s, 4.45, 1.65, 4.75, 4.65, C.white, { line: C.teal, dash: "dash", lineWidth: 1.5 });
  text(s, "SERVICE HOST — CPU only, in Docker (separate machine)", 4.6, 1.7, 4.5, 0.3, { size: 10, bold: true, color: C.teal });
  box(s, 4.65, 2.1, 2.15, 2.3, C.tealLight);
  text(s, [{ text: "Triage service", options: { bold: true, breakLine: true, fontSize: 13 } },
           { text: `FastAPI + uvicorn, ${a.uvicorn_workers} worker`, options: { breakLine: true } },
           { text: `thread pool ${a.threadpool}`, options: { breakLine: true } },
           { text: "no concurrency limit, no cache, no queue", options: { breakLine: true } },
           { text: `prompt ${a.prompt_hash}` }], 4.72, 2.15, 2.0, 2.2, { size: 10.5, para: 3 });
  s.addShape(pres.ShapeType.line, { x: 6.85, y: 3.25, w: 0.35, h: 0, line: { color: C.teal, width: 2, endArrowType: "triangle" } });
  box(s, 7.25, 2.1, 1.8, 2.3, C.amberLight);
  text(s, [{ text: "Ollama", options: { bold: true, breakLine: true, fontSize: 13 } },
           { text: "one pinned model", options: { breakLine: true } },
           { text: `num_ctx ${a.num_ctx}, temperature 0, seed ${a.seed}`, options: { breakLine: true } },
           { text: `timeout ${a.ollama_timeout_s} s`, options: { breakLine: true } },
           { text: "no GPU" }], 7.32, 2.15, 1.7, 2.2, { size: 10.5, para: 3 });
  box(s, 4.65, 4.6, 2.15, 1.5, C.light);
  text(s, [{ text: "SQLite", options: { bold: true, breakLine: true } }, { text: "named volume, emptied before every run" }], 4.72, 4.65, 2.0, 1.4, { size: 10.5 });
  box(s, 7.0, 4.6, 2.05, 1.5, C.light);
  text(s, [{ text: "Request log", options: { bold: true, breakLine: true } }, { text: "one JSONL line per request, 24 fields incl. Ollama's own timings" }],
       7.07, 4.65, 1.92, 1.4, { size: 10.5 });
  // endpoints
  const rows = [["Endpoint", "What it does"],
    ["POST /tickets", "Classifies one narrative by calling Ollama, stores it, returns the category. Synchronous: no answer until the model has answered. Model failure → HTTP 502, nothing stored."],
    ["GET /search?q=", "Returns stored tickets whose narrative contains the text (case-insensitive LIKE, full scan, limit 50)."],
    ["GET /stats", "Counts of stored tickets per category, including UNPARSEABLE and zero counts."],
    ["GET /health", "Model tag and digest, num_ctx, prompt hash, Ollama reachability. Not logged."]];
  table(s, rows, 9.45, 1.65, 3.33, [1.08, 2.25], { size: 10, headSize: 10.5 });
  box(s, MX, 5.05, 3.75, 1.65, C.dark);
  text(s, [{ text: "Baseline, deliberately naive", options: { bold: true, color: C.amber, breakLine: true } },
           { text: "Synchronous, sequential calls, no caching and no queuing. The service starts empty; tickets enter only through POST /tickets — the dataset is never bulk-loaded.", options: { color: C.white } }],
       MX + 0.1, 5.12, 3.55, 1.5, { size: 11.5 });
})();

// ======================================================== SLIDE 3 workload ===
(() => {
  const f = D.workload.figures;
  const g = (name) => f[name] ?? {};
  const s = frame("Workload model",
    "A modelled mid-sized firm receives about 1,500 complaint tickets a year, so every tested rate is far above its peak.",
    "workload/workload_model.md (Part 4); [27] CFPB 2025 Consumer Response Annual Report; [28] CNA (2024); [29] Whitt (2007); [26] workload/output/ (measured)");
  const cards = [
    { big: `${g("Tickets received per year").value}`, unit: "tickets / year", kind: "ESTIMATE",
      note: `${g("Complaint volume, published base figure").value} complaints sent to companies in 2025 [27] × equal share 1 ÷ 4,000 companies (0.025%).` },
    { big: `${g("Average (baseline) ticket arrival rate").value} → ${g("Peak ticket arrival rate").value}`, unit: "tickets / minute, average → peak", kind: "ESTIMATE",
      note: `${g("Tickets received per working day (average)").value} per working day over 8 opening hours; peak factor ${g("Peak factor (peak rate ÷ average rate)").value}× during daytime hours (assumed, call-centre profile [29]).` },
    { big: `${g("Agent search rate").value}`, unit: "agent searches / minute", kind: "ESTIMATE",
      note: `${g("Agents handling triage at one time").value} agents × ${g("Searches per agent per hour").value} searches/hour — one search per call, 4–5 calls/hour per officer [28]. ${g("Search-to-ticket ratio").value} searches per ticket.` },
    { big: "1 · 4 · 12", unit: "tested arrival rates, tickets / minute", kind: "CITED",
      note: "1/min is the lowest rate the harness runs (≈ 42× the modelled peak); 12/min = 720 tickets/hour is the capacity test. Searches tested at 1/min." },
  ];
  cards.forEach((c, i) => {
    const x = MX + (i % 2) * 3.55, y = 1.6 + Math.floor(i / 2) * 2.55;
    box(s, x, y, 3.4, 2.4, C.light);
    badge(s, c.kind === "CITED" ? "WORKLOAD → TEST" : c.kind, x + 0.15, y + 0.15, c.kind === "CITED" ? "CITED" : c.kind);
    text(s, c.big, x + 0.15, y + 0.45, 3.1, 0.6, { face: HEAD, size: 26, bold: true, color: C.dark, margin: 0 });
    text(s, c.unit, x + 0.15, y + 1.03, 3.1, 0.3, { size: 11, color: C.teal, bold: true, margin: 0 });
    text(s, c.note, x + 0.15, y + 1.33, 3.1, 1.0, { size: 10.5, color: C.ink, margin: 0 });
  });
  // length distribution
  const L = D.workload.lengths;
  box(s, 7.85, 1.6, 4.93, 5.1, C.white, { line: C.line });
  badge(s, "MEASURED", 8.0, 1.72, "MEASURED");
  text(s, "Ticket length — our own 1,000 team rows", 9.05, 1.68, 3.7, 0.32, { size: 12, bold: true, color: C.ink, margin: 0 });
  s.addImage({ path: path.join(REPO, D.workload.histogram), x: 8.05, y: 2.1, w: 4.55, h: 3.7 });
  const c = L.chars ?? {}, t = L.approx_tokens ?? {};
  text(s, `Median ${fmt(Number(c.p50), 1)} characters (≈ ${fmt(Number(t.p50))} tokens), p95 ${fmt(Number(c.p95), 0)}, max ${fmt(Number(c.max))}. No row risks truncation at num_ctx ${D.architecture.num_ctx}.`,
       8.05, 5.85, 4.6, 0.75, { size: 10.5 });
})();

// ==================================================== SLIDE 4 requirements ===
(() => {
  const R = D.requirements;
  const s = frame("Performance and accuracy requirements",
    "Testable statements derived from the workload model; accuracy is strict because a misrouted ticket costs more than a slow one.",
    "workload/requirements.md (Part 4). Load requirements are judged on the worst of the three runs; UNPARSEABLE counts as wrong.");
  const short = {
    R1: "An agent waiting at the screen should get a routing answer within 10 s; tested at 1/min, about 42× the modelled peak.",
    R2: "12/min = 720 tickets/hour, about 500× the modelled peak: the service must clear what arrives, finishing within 60 s of the last arrival.",
    R3: "At about 1,500 tickets a year, 90% means at most about 150 misrouted tickets a year, each handled twice.",
    R4: "Stops a strong overall figure hiding a failing category; one floor because the client ranks no category above another.",
    R5: "Agents search while classification runs; with about 10 stored tickets this tests contention with Ollama, not scan cost.",
  };
  const rows = [["ID", "Requirement (metric, threshold, percentile)", "Load condition", "Why this number"]];
  for (const r of R.rows) {
    const id = r.ID;
    const pctl = r.Percentile && r.Percentile !== "n/a" ? ` at ${r.Percentile}` : "";
    rows.push([{ text: id, bold: true, align: "center" }, `${r.Metric}: ${r.Threshold}${pctl}`, r["Load condition"].replace(/\s*Measured in a single serial pass.*$/, ""), short[id] ?? ""]);
  }
  table(s, rows, MX, 1.55, W - 2 * MX, [0.55, 3.35, 4.1, 4.23], { size: 10.5, headSize: 11 });
  box(s, MX, 5.75, W - 2 * MX, 0.95, C.dark);
  text(s, [{ text: "Position: ", options: { bold: true, color: C.amber } },
           { text: `${R.position} `, options: { color: C.white } },
           { text: "If no candidate meets everything, concede R5 first, then R2, then R1; R3 and R4 last.", options: { color: "9FB7BE" } }],
       MX + 0.15, 5.8, W - 2 * MX - 0.3, 0.85, { size: 13, valign: "middle" });
})();

// ========================================================== SLIDE 5 models ===
(() => {
  const s = frame("Candidate models",
    "Four CPU-feasible models across three size classes make the speed-versus-accuracy trade-off visible; each is pinned by tag and digest.",
    "models/models.yaml (digests written by scripts/pull_and_pin_models.sh), models/candidates.md; licences in [references]");
  const why = {
    "llama3.2:1b-instruct-q4_K_M": "Floor: how cheap can we go before instruction-following breaks?",
    "llama3.2:3b": "Same family one size up: isolates the effect of size.",
    "granite4:3b": "Same size, Apache-2.0: does a licence-clean model cost accuracy?",
    "qwen2.5:7b": "Ceiling: largest honestly CPU-servable model; in the set to be slow.",
  };
  const rows = [["Ollama tag", "Digest (sha256, first 12)", "Parameters", "Quantisation", "Size class", "Licence", "In the set to test"]];
  for (const m of D.models) {
    rows.push([{ text: m.tag, bold: true }, m.digest ? { text: shortDigest(m.digest), size: 10 } : { text: "pending pin", color: C.amber, bold: true },
      m.parameters, m.quantisation, m.size_class, m.licence.replace(" (custom, not OSI-approved)", " (custom)"), why[m.tag] ?? ""]);
  }
  table(s, rows, MX, 1.55, 8.45, [1.15, 1.45, 0.95, 1.0, 0.85, 1.25, 1.8], { size: 10, headSize: 10.5 });
  const params = D.models.map((m) => parseFloat(m.parameters));
  s.addChart(pres.ChartType.bar, [{ name: "Parameters (billions)", labels: D.models.map((m) => m.tag), values: params }], {
    x: 9.2, y: 1.5, w: 3.6, h: 3.1, barDir: "bar", chartColors: [C.teal], showValue: true, dataLabelFormatCode: "0.00\"B\"",
    dataLabelFontSize: 10, dataLabelFontFace: BODY, catAxisLabelFontSize: 10, catAxisLabelFontFace: BODY, valAxisHidden: true,
    valGridLine: { style: "none" }, catGridLine: { style: "none" }, showLegend: false, showTitle: true,
    title: "Parameters (billions)", titleFontSize: 11, titleFontFace: BODY, titleColor: C.ink, catAxisOrientation: "maxMin" });
  box(s, MX, 4.9, 8.45, 1.8, C.light);
  text(s, [{ text: "Notes for the reader", options: { bold: true, color: C.teal, breakLine: true } },
           { text: "All four at Q4_K_M: we pinned llama3.2:1b-instruct-q4_K_M rather than the bare llama3.2:1b tag (Ollama ships that at Q8_0), so the Llama 1B-versus-3B pair varies size alone.", options: { bullet: true, breakLine: true } },
           { text: "Rejected on purpose: qwen2.5:3b (Qwen Research licence, non-commercial), Qwen3 (thinking mode floods a one-word reply), Gemma (pass-through use terms), anything above 8B (not CPU-servable).", options: { bullet: true } }],
       MX + 0.1, 4.95, 8.25, 1.7, { size: 11, para: 4 });
  box(s, 9.2, 4.9, 3.58, 1.8, C.dark);
  const ov = D.models.find((m) => m.ollama_version)?.ollama_version;
  text(s, [{ text: "CPU only, one model at a time", options: { bold: true, color: C.amber, breakLine: true } },
           { text: `Served by Ollama ${ov ?? "(version from the pin)"} in Docker with no GPU device. The same tag and digest are recorded in every run's metadata.json.`, options: { color: C.white } }],
       9.3, 4.95, 3.4, 1.7, { size: 11 });
})();

// ========================================================== SLIDE 6 golden ===
(() => {
  const g = D.golden;
  const s = frame("Golden test set",
    `${g.rows} tickets labelled independently by two people, every disagreement resolved by discussion, frozen before the first benchmark.`,
    "labelling/protocol.md (revision log), labeller_A.csv, labeller_B.csv, agreement_report.txt, resolutions.md/.csv; golden/golden_set.csv; freeze: git tag golden-freeze");
  const stats = [
    { big: String(g.rows), unit: "tickets", note: `random sample of team rows 10000–10999 (seed ${g.sample_seed}); 19–41 per category` },
    { big: `κ = ${fmt(g.kappa, 3)}`, unit: `Cohen's kappa (${g.kappa_band})`, note: `${g.agreed} of ${g.rows} labels agreed (${pct(g.po, 0)}) before discussion` },
    { big: String(g.disagreements), unit: "disagreements, all resolved", note: `${g.resolutions} recorded resolutions; ${g.revisions.length - 1} rule revisions (R1–R6)` },
  ];
  stats.forEach((c, i) => {
    const x = MX + i * 2.75;
    box(s, x, 1.55, 2.6, 1.55, C.light);
    text(s, c.big, x + 0.12, 1.6, 2.4, 0.6, { face: HEAD, size: 26, bold: true, color: C.dark, margin: 0 });
    text(s, c.unit, x + 0.12, 2.17, 2.4, 0.3, { size: 11, bold: true, color: C.teal, margin: 0 });
    text(s, c.note, x + 0.12, 2.45, 2.4, 0.6, { size: 10, margin: 0 });
  });
  const pairs = g.top_pairs;
  const short = (c) => ({ "Bank account or service": "Bank account", "Money transfer or service": "Money transfer", "Credit reporting": "Credit reporting",
    "Credit card": "Credit card", "Consumer loan": "Consumer loan", "Debt collection": "Debt collection", "Mortgage": "Mortgage" }[c] ?? c);
  s.addChart(pres.ChartType.bar, [{ name: "Disagreements", labels: pairs.map((p) => `${short(p.pair[0])} ↔ ${short(p.pair[1])}`), values: pairs.map((p) => p.count) }], {
    x: 8.85, y: 1.45, w: 3.95, h: 2.75, barDir: "bar", chartColors: [C.amber], showValue: true, dataLabelFontSize: 10, dataLabelFontFace: BODY,
    catAxisLabelFontSize: 9.5, catAxisLabelFontFace: BODY, valAxisHidden: true, valGridLine: { style: "none" }, catGridLine: { style: "none" },
    showLegend: false, showTitle: true, title: "Where the two labellers disagreed most", titleFontSize: 11, titleFontFace: BODY, titleColor: C.ink, catAxisOrientation: "maxMin" });
  // revisions
  const revRows = [["Rev.", "Protocol change (2 Oct)", "Rows"]];
  for (const r of g.revisions) {
    const rowsCaused = r["Which disagreement prompted it"];
    const n = rowsCaused && /\d/.test(rowsCaused) ? `${rowsCaused.split(",").length}` : "—";
    const change = r["What changed"].length > 150 ? r["What changed"].slice(0, 147).replace(/\s+\S*$/, "") + "…" : r["What changed"];
    revRows.push([{ text: r.Revision, bold: true, align: "center" }, change, { text: n, align: "center" }]);
  }
  table(s, revRows, MX, 3.25, 8.15, [0.5, 7.0, 0.65], { size: 9, headSize: 9.5, margin: [2, 4, 2, 4] });
  // examples
  g.examples.slice(0, 2).forEach((e, i) => {
    const y = 4.3 + i * 1.22;
    box(s, 8.85, y, 3.95, 1.12, i ? C.tealLight : C.amberLight);
    const reason = e.reasoning.split(". Settled by")[0];
    text(s, [{ text: `Row ${e.row}: `, options: { bold: true } },
             { text: `${short(e.label_a)} vs ${short(e.label_b)} → `, options: {} },
             { text: `${e.agreed}`, options: { bold: true, color: C.teal } },
             { text: ` (${e.revision}). `, options: { color: C.muted } },
             { text: reason.length > 175 ? reason.slice(0, 172).replace(/\s+\S*$/, "") + "…" : reason, options: { color: C.ink } }],
         8.92, y + 0.03, 3.82, 1.06, { size: 9.5 });
  });
  text(s, "R0 is the first full write-up of the definitions and edge-case rules; it was completed after both sheets were labelled, from the resolutions, and is recorded as such.",
       MX, 6.62, 8.15, 0.35, { size: 9, italic: true, color: C.muted, margin: 0 });
})();

// ===================================================== SLIDE 7 environment ===
(() => {
  const E = D.environment;
  const s = frame("Test environment",
    "Two physically separate machines: the service and Ollama on a CPU-only desktop, JMeter on a laptop.",
    "docs/environment/*.txt (scripts/capture_env.sh), docs/environment/network.md, docs/test-environment.md; hostnames in every run's metadata.json");
  const svc = E.hosts.find((h) => /^(service|ollama|all)/.test(h.role ?? ""));
  const lg = E.hosts.find((h) => h.role === "loadgen");
  const card = (h, x, title, pendingText) => {
    box(s, x, 1.55, 4.0, 3.15, C.light);
    text(s, title, x + 0.12, 1.62, 3.8, 0.3, { size: 11, bold: true, color: C.teal });
    if (!h) { pending(s, x + 0.15, 2.05, 3.7, 1.0, pendingText); return; }
    const lines = [
      ["Host", h.host], ["CPU", h.cpu], ["Cores / threads", `${h.physical_cores ?? "–"} / ${h.logical_cpus ?? "–"}`],
      ["Memory", h.ram], ["OS", [h.os, h.kernel].filter(Boolean).join(", ")], ["Docker", h.docker],
      h.role === "loadgen" ? ["JMeter / Java", `JMeter ${h.jmeter} on OpenJDK 21 (bin/setenv.sh)`] : ["Ollama", (h.ollama ?? "").replace(/[{}"]|version:/g, "")],
    ];
    const rows = lines.map(([k, v]) => [{ text: k, options: { bold: true, color: C.muted, fontSize: 10 } }, { text: String(v ?? "–"), options: { color: C.ink, fontSize: 10 } }]);
    s.addTable(rows, { x: x + 0.1, y: 1.95, w: 3.8, colW: [1.1, 2.7], fontFace: BODY, border: { type: "none" }, margin: [2, 3, 2, 3], autoPage: false });
  };
  card(svc, MX, "SERVICE + OLLAMA HOST (system under test)", "service-host capture (scripts/capture_env.sh --role all on the desktop)");
  card(lg, MX + 4.15, "LOAD GENERATOR (JMeter, accuracy driver)", "load-generator capture (scripts/capture_env.sh --role loadgen on the MacBook)");
  box(s, MX + 8.3, 1.55, 3.93, 3.15, C.dark);
  const net = E.network_md ? E.network_md.split("\n").filter((l) => l.startsWith("- ")).slice(0, 4).map((l) => l.slice(2)) : null;
  text(s, [{ text: "Separate machines, measured network", options: { bold: true, color: C.amber, breakLine: true } },
           ...(net ? net.map((l, i) => ({ text: l, options: { color: C.white, bullet: true, breakLine: i < net.length - 1 } }))
                   : [{ text: "PENDING — round trip and link type are measured once both machines are up.", options: { color: C.amber } }])],
       MX + 8.42, 1.62, 3.7, 3.0, { size: 11, para: 4 });
  box(s, MX, 4.85, W - 2 * MX, 1.85, C.white, { line: C.line });
  text(s, [{ text: "How the results carry over to the client, and what could make them unrepresentative", options: { bold: true, color: C.teal, breakLine: true } },
           { text: "Scaling assumption: CPU inference time is set by cores and memory bandwidth. A commodity server with more cores and memory channels than our desktop should be faster per request; we report our hardware so the client can scale, and do not claim their numbers.", options: { bullet: true, breakLine: true } },
           { text: "One model and one request at a time per model (Ollama default): a server with more RAM could hold more models but not run one model faster.", options: { bullet: true, breakLine: true } },
           { text: "Limitations: a personal desktop with a desktop session (variance biased up, mostly in p95/p99); a desktop CPU at up to 4.95 GHz but only two memory channels; a single service host, so no claim about horizontal scaling; Poisson arrivals, so each run's ticket count varies (spread shown).", options: { bullet: true } }],
       MX + 0.1, 4.9, W - 2 * MX - 0.2, 1.75, { size: 10.5, para: 3 });
})();

// ======================================================== SLIDE 8 playbook ===
(() => {
  const s = frame("Playbook: how every test was run",
    "One script runs every configuration identically; open-loop arrivals, an empty database, a warm-up excluded from the numbers, three runs each.",
    "docs/playbooks/load-test.md, stress-test.md, accuracy-test.md; scripts/run_campaign.sh, scripts/run_load_test.sh, scripts/run_accuracy.py; jmeter/*.jmx");
  const steps = [
    ["1 Freeze gate", "scripts/freeze_gate.py must pass: golden set and predictions committed and tagged"],
    ["2 Reset", "database volume deleted; service restarted empty"],
    ["3 Switch model", "MODEL_TAG set; /health must report the model and its pinned digest"],
    ["4 Warm-up", "one synthetic ticket pays the model-load cost; excluded from every figure"],
    ["5 JMeter, open loop", "Poisson arrivals at a fixed rate; 150 s drain lets in-flight requests finish"],
    ["6 Evidence", "results.jtl, the service log slice, metadata.json and freeze.json per run"],
    ["7 Reconcile, analyse", "every .jtl sample joined to its log line on request_id, then summarised"],
  ];
  const bw = (W - 2 * MX - 0.1 * 6) / 7;
  steps.forEach(([t, d], i) => {
    const x = MX + i * (bw + 0.1);
    box(s, x, 1.55, bw, 1.75, i === 4 ? C.dark : C.tealLight);
    text(s, t, x + 0.05, 1.6, bw - 0.1, 0.45, { size: 11.5, bold: true, color: i === 4 ? C.amber : C.dark });
    text(s, d, x + 0.05, 2.05, bw - 0.1, 1.2, { size: 9.5, color: i === 4 ? C.white : C.ink });
  });
  box(s, MX, 3.45, W - 2 * MX, 0.62, C.light);
  text(s, [{ text: "Open Model Thread Group schedule: ", options: { bold: true, color: C.teal } },
           { text: "rate(${rate_per_min}/min) random_arrivals(600 sec) pause(150 sec)", options: { fontFace: "Courier New", color: C.ink } },
           { text: "   — closed-loop thread groups are never used: they self-throttle and hide queue build-up.", options: { color: C.muted } }],
       MX + 0.1, 3.48, W - 2 * MX - 0.2, 0.56, { size: 11, valign: "middle" });
  const tests = [
    ["Load", "load_post_tickets at 1, 4 and 12 tickets/min; 600 s each; 3 runs per rate per model (36 runs)"],
    ["Mixed", "mixed_load: 1 ticket/min + 1 search/min, 600 s, 3 runs per model; GET /search judged separately (R5)"],
    ["Stress", "stress_ramp: 1, 5, 9, 13, 17, 21 tickets/min, 120 s per step + 150 s drain; once per model; limit = first step with p95 > 10 s or > 5% errors"],
    ["Accuracy", "all 200 golden tickets, one at a time, once per model; the driver never reads the labels; scored afterwards by analysis/accuracy.py"],
  ];
  tests.forEach(([t, d], i) => {
    const x = MX + (i % 2) * 6.17, y = 4.25 + Math.floor(i / 2) * 1.0;
    box(s, x, y, 6.05, 0.9, C.white, { line: C.line });
    text(s, [{ text: `${t}  `, options: { bold: true, color: C.teal } }, { text: d, options: { color: C.ink } }], x + 0.1, y + 0.03, 5.85, 0.84, { size: 10.5, valign: "middle" });
  });
  text(s, [{ text: "Reproduce: ", options: { bold: true, color: C.teal } },
           { text: "SERVICE_SSH=<user>@<host> TARGET_HOST=<host> scripts/run_campaign.sh", options: { fontFace: "Courier New" } },
           { text: "  then  ", options: {} },
           { text: "scripts/run_analysis.sh", options: { fontFace: "Courier New" } }],
       MX, 6.3, W - 2 * MX, 0.35, { size: 10.5, margin: 0 });
})();

// ===================================================== SLIDE 9 load/stress ===
const N = D.narrative ?? {};
const shortTag = (t) => t.replace("-instruct-q4_K_M", " q4_K_M");
const secs = (v) => (v === null || v === undefined || Number.isNaN(v)) ? "–" : (v >= 1000 ? `${fmt(v / 1000, v >= 100000 ? 0 : 1)} s` : `${fmt(v)} ms`);
const spread = (m) => `${secs(m.mean)} (${secs(m.min)}–${secs(m.max)})`;
(() => {
  const s = frame("Load and stress test results", N.slide9_message ?? null,
    "analysis/output/load/load_per_run.csv — mean (min–max) of three runs; analysis/output/stress/, analysis/output/bottleneck/; every run reconciled (analysis/output/reconcile/SUMMARY.md)");
  if (!D.load.configs.length) {
    pending(s, MX, 1.6, W - 2 * MX, 1.0, "the benchmark campaign has not finished; this slide fills from analysis/output/ when it has.");
    return;
  }
  const rows = [["Model", "Rate /min", "p50", "p95", "p99", "OK tickets /h", "Errors"]];
  for (const tag of MODEL_ORDER) {
    const cfgs = D.load.configs.filter((c) => c.model === tag && c.plan === "load_post_tickets").sort((a, b) => a.rate - b.rate);
    cfgs.forEach((cfg, i) => {
      const r1fail = cfg.rate === 1 && cfg.client_p95_ms.max > 10000;
      const r2fail = cfg.rate === 12 && (cfg.error_rate_pct.max > 5 || cfg.span_s.max > 660);
      rows.push([i === 0 ? { text: shortTag(tag), bold: true } : "", { text: String(cfg.rate), align: "center" },
        spread(cfg.client_p50_ms),
        { text: spread(cfg.client_p95_ms), color: r1fail ? C.fail : C.ink, bold: r1fail },
        spread(cfg.client_p99_ms),
        { text: `${fmt(cfg.ok_throughput_per_hour.mean)} (${fmt(cfg.ok_throughput_per_hour.min)}–${fmt(cfg.ok_throughput_per_hour.max)})`, align: "center", color: r2fail ? C.fail : C.ink, bold: r2fail },
        { text: `${fmt(cfg.error_rate_pct.mean, 1)}%${cfg.error_rate_pct.max > 0 ? ` (max ${fmt(cfg.error_rate_pct.max, 1)})` : ""}`, align: "center", color: cfg.error_rate_pct.max > 5 ? C.fail : C.ink, bold: cfg.error_rate_pct.max > 5 }]);
    });
  }
  table(s, rows, MX, 1.5, 8.05, [1.3, 0.6, 1.4, 1.45, 1.4, 1.1, 0.8], { size: 8.5, headSize: 9, margin: [1.5, 3, 1.5, 3] });
  text(s, "Red: fails R1 (worst-run p95 > 10 s at 1/min) or R2 (> 5% errors, or a run not finished within 660 s, at 12/min).",
       MX, 5.2, 8.05, 0.25, { size: 8.5, italic: true, color: C.muted, margin: 0 });

  // stress: p95 per offered step, one series per model (log axis)
  const stress = D.stress.filter((r) => r.steps && r.steps.length);
  if (stress.length) {
    const primary = stress.filter((r) => Number(r.steps[0].offered_per_min) <= 1);
    const labels = (primary[0] ?? stress[0]).steps.map((st) => String(st.offered_per_min));
    const series = primary.map((r) => ({ name: shortTag(r.model), labels, values: r.steps.map((st) => Math.max(0.1, Number(st.p95_ms) / 1000)) }));
    s.addChart(pres.ChartType.line, series, { x: 8.75, y: 1.42, w: 4.05, h: 2.45, chartColors: [C.teal, C.amber, "6C5B7B", C.fail],
      lineSize: 2, lineDataSymbolSize: 5, valAxisLogScaleBase: 10, valAxisTitle: "p95 (s, log)", showValAxisTitle: true, valAxisTitleFontSize: 9,
      catAxisTitle: "offered tickets / min (120 s steps)", showCatAxisTitle: true, catAxisTitleFontSize: 9, catAxisLabelFontSize: 9, valAxisLabelFontSize: 9,
      showLegend: true, legendPos: "b", legendFontSize: 8.5, showTitle: true, title: "Stress ramp: p95 per step", titleFontSize: 10.5, titleFontFace: BODY,
      valGridLine: { color: "E3E9EA", size: 0.5 }, catGridLine: { style: "none" } });
    const lim = [["Model", "Limit found (first step with p95 > 10 s or > 5% errors)"]];
    for (const tag of MODEL_ORDER) {
      for (const r of stress.filter((x) => x.model === tag)) {
        lim.push([{ text: shortTag(tag), bold: true }, { text: r.limit_short ?? r.limit, size: 8 }]);
      }
    }
    table(s, lim, 8.75, 3.95, 4.05, [1.15, 2.9], { size: 8, headSize: 8.5, margin: [1.5, 3, 1.5, 3] });
  } else {
    pending(s, 8.75, 1.5, 4.05, 1.2, "stress ramp results");
  }
  box(s, MX, 5.5, W - 2 * MX, 1.5, C.dark);
  text(s, [{ text: "Bottleneck, diagnosed: ", options: { bold: true, color: C.amber } },
           { text: N.slide9_bottleneck ?? "PENDING — interpretation written once the bottleneck analysis exists.", options: { color: C.white } }],
       MX + 0.12, 5.55, W - 2 * MX - 0.24, 1.4, { size: 10.5, valign: "middle" });
})();

// ======================================================== SLIDE 10 accuracy ===
(() => {
  const s = frame("Accuracy results", N.slide10_message ?? null,
    "analysis/output/accuracy/ (model_comparison.csv; <run>/per_category.csv and confusion_matrix.csv) — 200 golden tickets, one serial pass per model; UNPARSEABLE counted as wrong");
  if (!D.accuracy.length) {
    pending(s, MX, 1.6, W - 2 * MX, 1.0, "the accuracy runs have not been analysed yet.");
    return;
  }
  const cats = D.architecture.categories;
  const abbrev = { "Credit reporting": "Credit report.", "Debt collection": "Debt coll.", "Mortgage": "Mortgage", "Credit card": "Credit card",
    "Bank account or service": "Bank acct", "Consumer loan": "Cons. loan", "Money transfer or service": "Money transf." };
  const head = ["Model", "Overall (R3 ≥ 90%)", ...cats.map((c) => `${abbrev[c]} (${D.golden.counts[c]})`), "UNPARS."];
  const rows = [head];
  const byModel = Object.fromEntries(D.accuracy.map((a) => [a.model_tag, a]));
  for (const tag of MODEL_ORDER) {
    const a = byModel[tag];
    if (!a) { rows.push([{ text: shortTag(tag), bold: true }, { text: "pending", color: C.amber }, ...cats.map(() => ""), ""]); continue; }
    const pc = Object.fromEntries(a.per_category.map((c) => [c.category, c]));
    rows.push([{ text: shortTag(tag), bold: true },
      { text: `${pct(a.accuracy, 1)} (${a.correct}/${a.golden_rows})`, bold: true, align: "center", fill: a.accuracy >= 0.9 ? C.passLight : C.failLight, color: a.accuracy >= 0.9 ? C.pass : C.fail },
      ...cats.map((c) => { const r = Number(pc[c]?.recall); return { text: Number.isNaN(r) ? "–" : pct(r, 0), align: "center", fill: r >= 0.8 ? C.passLight : C.failLight, color: r >= 0.8 ? C.pass : C.fail }; }),
      { text: String(a.unparseable ?? 0), align: "center" }]);
  }
  table(s, rows, MX, 1.5, W - 2 * MX, [1.45, 1.45, ...cats.map(() => 1.18), 0.7], { size: 9.5, headSize: 9, margin: [2, 3, 2, 3] });
  text(s, "Cells are per-category recall (R4 ≥ 80%): the share of golden tickets in that category the model routed correctly. Green meets the requirement, red does not.",
       MX, 2.88, W - 2 * MX, 0.26, { size: 9, italic: true, color: C.muted, margin: 0 });
  // where each model goes wrong: 2 x 2 grid, then the best model's confusion matrix
  const predHard = Object.fromEntries((D.predictions.rows ?? []).map((r) => [r.model, (r["Expected hardest category"] ?? "").replace(/\s*—.*$/, "")]));
  const bw = 3.95, bh = 1.32;
  MODEL_ORDER.forEach((tag, i) => {
    const a = byModel[tag];
    const x = MX + (i % 2) * (bw + 0.1), y = 3.22 + Math.floor(i / 2) * (bh + 0.08);
    box(s, x, y, bw, bh, i % 3 ? C.light : C.tealLight);
    const worst = a ? [...a.per_category].filter((c) => c.recall !== null).sort((p, q) => p.recall - q.recall)[0] : null;
    const lines = [{ text: `${shortTag(tag)}`, options: { bold: true, color: C.dark, breakLine: true } }];
    if (worst) lines.push({ text: `Hardest: ${abbrev[worst.category] ?? worst.category} ${pct(worst.recall, 0)} (predicted: ${predHard[tag] ?? "–"})`, options: { color: C.teal, breakLine: true } });
    (a?.top_confusions ?? []).slice(0, 3).forEach((c, k, arr) => lines.push({ text: `${c.count} × ${abbrev[c.golden] ?? c.golden} → ${abbrev[c.predicted] ?? c.predicted}`, options: { breakLine: k < arr.length - 1 } }));
    text(s, lines, x + 0.08, y + 0.04, bw - 0.16, bh - 0.08, { size: 9.5, para: 1 });
  });
  const best = [...D.accuracy].sort((p, q) => q.accuracy - p.accuracy)[0];
  if (best) {
    const img = path.join(REPO, best.run_dir, "confusion_matrix.png");
    if (fs.existsSync(img)) s.addImage({ path: img, x: 8.72, y: 3.18, w: 4.06, h: 2.74 });
  }
  box(s, MX, 6.0, W - 2 * MX, 1.0, C.dark);
  text(s, [{ text: "Reading: ", options: { bold: true, color: C.amber } },
           { text: N.slide10_reading ?? "PENDING — interpretation written once the accuracy analysis exists.", options: { color: C.white } }],
       MX + 0.12, 6.03, W - 2 * MX - 0.24, 0.94, { size: 10.5, valign: "middle" });
})();

// ===================================================== SLIDE 11 predictions ===
(() => {
  const s = frame("Predictions, recommendation and defence", N.slide11_message ?? null,
    `predictions: git tag golden-freeze (${D.predictions.source}); outcomes: analysis/output/; requirements: workload/requirements.md; full account: predictions/outcomes.md`);
  // requirement matrix
  const V = Object.fromEntries((D.verdicts ?? []).map((v) => [v.model, v]));
  const cell = (v, label) => v ? passCell(v.ok, label) : passCell(null);
  const rq = [["Model", "R1 p95 @1/min ≤ 10 s", "R2 12/min, ≤ 5% err, ≤ 660 s", "R3 overall ≥ 90%", "R4 every cat. ≥ 80%", "R5 search p95 ≤ 2 s"]];
  for (const tag of MODEL_ORDER) {
    const v = V[tag] ?? {};
    rq.push([{ text: shortTag(tag), bold: true },
      cell(v.R1, v.R1 ? secs(v.R1.value_ms) : null),
      cell(v.R2, v.R2 ? `${fmt(v.R2.error_pct, 1)}%, ${fmt(v.R2.span_s)} s` : null),
      cell(v.R3, v.R3 ? pct(v.R3.value, 1) : null),
      cell(v.R4, v.R4 ? `min ${pct(v.R4.min_recall, 0)}` : null),
      cell(v.R5, v.R5 ? secs(v.R5.value_ms) : null)]);
  }
  table(s, rq, MX, 1.45, 7.6, [1.3, 1.25, 1.5, 1.15, 1.2, 1.2], { size: 9.5, headSize: 8.5, margin: [2, 3, 2, 3] });
  // predictions vs outcomes
  const P = Object.fromEntries((D.predictions.rows ?? []).map((r) => [r.model, r]));
  const acc = Object.fromEntries(D.accuracy.map((a) => [a.model_tag, a]));
  const load1 = Object.fromEntries(D.load.configs.filter((c) => c.plan === "load_post_tickets" && c.rate === 1).map((c) => [c.model, c]));
  const pr = [["Model", "Accuracy: predicted → measured", "Warm p50: predicted → measured", "p95 @1/min: predicted → worst run"]];
  for (const tag of MODEL_ORDER) {
    const p = P[tag] ?? {};
    const accText = p["Expected overall accuracy (%)"] ?? "";
    const accM = accText.match(/(\d+)\s*\(accept\s*([\d–-]+)\)/);
    const predAcc = accM ? `${accM[1]}% (${accM[2]})${/not blind/.test(accText) ? "*" : ""}` : accText;
    const predP50 = (p["Expected single-request latency (p50, ms, warm)"] ?? "").replace(/,/g, "");
    const predP95 = (p["Expected p95 at the lowest tested rate, 1/min (R1's condition)"] ?? "").replace(/,/g, "");
    const a = acc[tag], l = load1[tag];
    pr.push([{ text: shortTag(tag), bold: true },
      `${predAcc} → ${a ? pct(a.accuracy, 1) : "–"}`,
      `${predP50 ? secs(Number(predP50)) : "–"} → ${l ? secs(l.client_p50_ms.mean) : "–"}`,
      `${predP95 ? secs(Number(predP95)) : "–"} → ${l ? secs(l.client_p95_ms.max) : "–"}`]);
  }
  table(s, pr, MX, 2.85, 7.6, [1.3, 2.1, 2.1, 2.1], { size: 9.5, headSize: 9, margin: [2, 3, 2, 3] });
  text(s, "* not blind: the drafter had seen an excluded pre-prediction run's category counts (prediction record §0).", MX, 4.17, 7.6, 0.25, { size: 8, italic: true, color: C.muted, margin: 0 });
  text(s, [{ text: "Where we were wrong, and why: ", options: { bold: true, color: C.teal } },
           { text: N.slide11_wrong ?? "PENDING — written once outcomes exist.", options: { color: C.ink } }],
       MX, 4.47, 7.6, 2.53, { size: 10, valign: "top" });
  // recommendation
  box(s, 8.4, 1.45, 4.38, 5.55, C.dark);
  text(s, [{ text: "Recommendation", options: { bold: true, color: C.amber, fontSize: 13, breakLine: true } },
           { text: N.recommendation ?? "PENDING — the recommended model, defended requirement by requirement.", options: { color: C.white, breakLine: true } },
           { text: " ", options: { breakLine: true, fontSize: 6 } },
           { text: "Requirements no candidate meets", options: { bold: true, color: C.amber, breakLine: true } },
           { text: N.unmet ?? "PENDING", options: { color: C.white } }],
       8.52, 1.52, 4.15, 5.4, { size: 10.5, para: 3 });
})();

// ====================================================== SLIDE 12 references ===
(() => {
  const s = frame("References and acknowledgements", null, "docs/references.md (IEEE style); NOTICE");
  const refs = D.references;
  if (!refs.length) {
    pending(s, MX, 1.5, W - 2 * MX, 0.8, "the reference list in docs/references.md.");
    return;
  }
  const half = Math.ceil(refs.length / 2);
  [refs.slice(0, half), refs.slice(half)].forEach((col, ci) => {
    text(s, col.map((r, i) => ({ text: `[${r.n}] ${r.text}`, options: { breakLine: i < col.length - 1 } })),
         MX + ci * 6.2, 1.1, 6.0, 4.75, { size: 8, para: 2 });
  });
})();

pres.writeFile({ fileName: OUT }).then((f) => console.log(`wrote ${path.relative(REPO, f)}`));
