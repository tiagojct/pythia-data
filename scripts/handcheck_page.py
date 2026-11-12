"""Hand check of the coder: a local page, and the score of the result.

    uv run scripts/handcheck_page.py                   # writes data/coded/handcheck.html
    uv run scripts/handcheck_page.py --score <file>    # agreement of a result file with the coder

The page reads nothing from the network. Open it in a browser from the file.
It shows one event of data/coded/handcheck.csv at a time, without the model
name. Keys 1, 2 and 3 mark the theme, the valence or the anchor as wrong. The
marks are kept in the browser. "Download result" writes a CSV with the columns
of handcheck.csv, the *_ok columns filled with y or n, and the corrections in
theme_fix, valence_fix and anchor_fix.
"""

import argparse
import csv
import html
import json
import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CODED = ROOT / "data" / "coded"


def themes() -> dict[str, str]:
    text = (ROOT / "coding" / "codebook.md").read_text()
    part = text.split("## Themes", 1)[1].split("## Valence", 1)[0]
    return dict(re.findall(r"^- ([a-z_]+): (.+)$", part, re.M))


def anchors() -> dict[str, str]:
    cfg = tomllib.loads((ROOT / "config.toml").read_text())
    return {a["id"]: a["text"] for a in cfg["anchors"]}


VALENCE = {
    "positive": "a gain, an achievement or a problem solved",
    "negative": "a loss, a harm, a danger or a failure",
    "neutral": "a change with no clear gain or loss, or a mix of both",
}


def page() -> None:
    rows = list(csv.DictReader((CODED / "handcheck.csv").open()))
    data = [{"key": f'{r["model"]}|{r["run"]}|{r["order"]}', "year": r["year"], "event": r["event"],
             "detail": r["detail"], "theme": r["theme"], "valence": r["valence"], "anchor": r["anchor"]}
            for r in rows]
    payload = json.dumps({"rows": data, "themes": themes(), "anchors": anchors(), "valence": VALENCE},
                         ensure_ascii=False).replace("</", "<\\/")
    out = TEMPLATE.replace("__DATA__", payload)
    (CODED / "handcheck.html").write_text(out)
    print(f"wrote {CODED / 'handcheck.html'}: {len(data)} events")


def score(path: Path) -> None:
    rows = list(csv.DictReader(path.open()))
    done = [r for r in rows if r["theme_ok"] in ("y", "n")]
    print(f"{len(done)} of {len(rows)} events checked")
    if not done:
        return
    for field in ("theme", "valence", "anchor"):
        ok = sum(r[f"{field}_ok"] == "y" for r in done)
        print(f"{field}: {ok} of {len(done)} correct ({100 * ok / len(done):.1f}%)")
    print("Codes marked wrong:")
    for r in done:
        for field in ("theme", "valence", "anchor"):
            if r[f"{field}_ok"] == "n":
                fix = r.get(f"{field}_fix", "") or "?"
                print(f'  {r["year"]} {r["event"][:60]!r}: {field} {r[field] or "none"} -> {fix}')


TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Pythia hand check</title>
<style>
@font-face { font-family: 'Source Serif 4'; font-weight: 300 700; src: url('../../site/fonts/sourceserif4.woff2') format('woff2'); }
@font-face { font-family: 'Courier Prime'; src: url('../../site/fonts/courierprime.woff2') format('woff2'); }
:root { --bg: #f7f6f2; --card: #ffffff; --ink: #1a1a1a; --soft: #3a3a37; --mute: #5c5b56; --rule: #d9d7cf;
  --spot: #b3301a; --wrong-bg: #fbe9e5; --ok: #1c5cab; --serif: 'Source Serif 4', Charter, Georgia, serif;
  --mono: 'Courier Prime', 'Courier New', monospace; color-scheme: light; }
@media (prefers-color-scheme: dark) {
  :root { --bg: #0e0f11; --card: #17191c; --ink: #e8ecee; --soft: #c9cdd0; --mute: #a3a8ac; --rule: #2c2f34;
    --spot: #ef6d52; --wrong-bg: #3a1d17; --ok: #86b6ef; color-scheme: dark; }
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--ink); font-family: var(--serif); font-size: 1.125rem; line-height: 1.5; }
main { max-width: 46rem; margin: 0 auto; padding: 2rem 16px 4rem; }
header { display: flex; flex-wrap: wrap; gap: .5rem 1rem; align-items: baseline; justify-content: space-between; font-family: var(--mono); font-size: .8125rem; color: var(--mute); }
.bar { height: 3px; background: var(--rule); margin: .6rem 0 2rem; }
.bar span { display: block; height: 100%; background: var(--spot); width: 0; }
.year { font-family: var(--mono); color: var(--mute); font-size: .875rem; }
h1 { font-size: 1.6rem; line-height: 1.2; margin: .2rem 0 .6rem; font-weight: 600; }
.detail { color: var(--soft); margin: 0 0 1.8rem; }
.code { background: var(--card); border: 1px solid var(--rule); border-radius: 6px; padding: .8rem 1rem; margin-bottom: .7rem; display: grid; grid-template-columns: 2.2rem minmax(0, 1fr) auto; gap: .2rem .8rem; align-items: start; }
.code.wrong { background: var(--wrong-bg); border-color: var(--spot); }
.k { font-family: var(--mono); font-size: .8125rem; border: 1px solid var(--rule); border-radius: 4px; text-align: center; padding: 2px 0; color: var(--mute); }
.name { font-family: var(--mono); font-size: .75rem; letter-spacing: .06em; color: var(--mute); text-transform: uppercase; }
.val { font-weight: 600; }
.def { font-size: .9375rem; color: var(--soft); }
.code button { font: .8125rem var(--mono); padding: .3rem .7rem; border: 1px solid var(--rule); border-radius: 4px; background: transparent; color: var(--ink); cursor: pointer; }
.code.wrong button { border-color: var(--spot); color: var(--spot); }
.fix { grid-column: 2 / 4; margin-top: .4rem; display: none; }
.code.wrong .fix { display: block; }
select, textarea { font: inherit; font-size: .9375rem; color: var(--ink); background: var(--card); border: 1px solid var(--rule); border-radius: 4px; padding: .3rem; max-width: 100%; }
textarea { width: 100%; min-height: 2.6rem; margin-top: .4rem; }
nav { display: flex; flex-wrap: wrap; gap: .6rem; margin-top: 1.4rem; }
nav button, .tools button, .tools label { font: .875rem var(--mono); padding: .5rem 1rem; border: 1px solid var(--ink); border-radius: 4px; background: var(--ink); color: var(--bg); cursor: pointer; }
nav button.secondary, .tools button, .tools label { background: transparent; color: var(--ink); border-color: var(--rule); }
.help { font-size: .875rem; color: var(--mute); margin-top: 2.5rem; border-top: 1px solid var(--rule); padding-top: 1rem; }
.tools { display: flex; flex-wrap: wrap; gap: .6rem; margin-top: 1rem; }
.tools input { display: none; }
.status { font-family: var(--mono); font-size: .8125rem; color: var(--ok); min-height: 1.2em; margin-top: .6rem; }
:focus-visible { outline: 2px solid var(--spot); outline-offset: 2px; }
</style>
</head>
<body>
<main>
  <header><span>Pythia: hand check of the coder</span><span id="count"></span></header>
  <div class="bar"><span id="bar"></span></div>
  <p class="year" id="year"></p>
  <h1 id="event"></h1>
  <p class="detail" id="detail"></p>
  <div id="codes"></div>
  <label class="name" for="note">Note (optional)</label>
  <textarea id="note"></textarea>
  <nav>
    <button class="secondary" id="prev">Back</button>
    <button id="next">Correct as marked, next</button>
  </nav>
  <div class="help">
    <p>Read the event. A code is correct if a careful reader with the codebook gives the same code. For each wrong code, press its key or its button. A correction is optional. An empty anchor means "no anchor", and it is correct when no anchor event says the same thing.</p>
    <p>Keys: 1, 2, 3 mark a code as wrong (press again to undo). Enter or right arrow: next. Left arrow: back. The marks stay in this browser. Download the result at the end and put it in data/coded/.</p>
    <div class="tools">
      <button id="download">Download result</button>
      <label for="load">Load a result file</label><input type="file" id="load" accept=".csv">
      <button id="first-open">Go to first unchecked</button>
    </div>
    <p class="status" id="status" role="status"></p>
  </div>
</main>
<script>
const D = __DATA__;
const KEY = "pythia-handcheck-v1";
const FIELDS = ["theme", "valence", "anchor"];
let state = { i: 0, marks: {} };
try { const s = JSON.parse(localStorage.getItem(KEY)); if (s && s.marks) state = s; } catch (e) {}
function save() { try { localStorage.setItem(KEY, JSON.stringify(state)); } catch (e) {} }
function mark(r) { return state.marks[r.key] || (state.marks[r.key] = { seen: false, wrong: {}, fix: {}, note: "" }); }
const $ = id => document.getElementById(id);
const esc = s => String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);

function options(field, current) {
  const src = field === "theme" ? D.themes : field === "valence" ? D.valence : D.anchors;
  let o = `<option value="">Correct code (optional)</option>`;
  if (field === "anchor") o += `<option value="none"${current === "none" ? " selected" : ""}>none: no anchor matches</option>`;
  for (const k of Object.keys(src)) o += `<option value="${k}"${current === k ? " selected" : ""}>${esc(k)}: ${esc(src[k]).slice(0, 90)}</option>`;
  return o;
}
function def(field, v) {
  if (field === "theme") return D.themes[v] || "";
  if (field === "valence") return D.valence[v] || "";
  return v ? D.anchors[v] || "" : "No anchor event says the same thing.";
}
function render() {
  const r = D.rows[state.i], m = mark(r);
  const done = D.rows.filter(x => state.marks[x.key] && state.marks[x.key].seen).length;
  $("count").textContent = `Event ${state.i + 1} of ${D.rows.length}. Checked: ${done}`;
  $("bar").style.width = (100 * done / D.rows.length) + "%";
  $("year").textContent = r.year;
  $("event").textContent = r.event;
  $("detail").textContent = r.detail;
  $("codes").innerHTML = FIELDS.map((f, n) => `
    <div class="code${m.wrong[f] ? " wrong" : ""}" data-f="${f}">
      <span class="k">${n + 1}</span>
      <div><div class="name">${f}</div><div class="val">${esc(r[f] || "none")}</div><div class="def">${esc(def(f, r[f]))}</div></div>
      <button type="button" aria-pressed="${!!m.wrong[f]}">${m.wrong[f] ? "Wrong" : "Mark wrong"}</button>
      <div class="fix"><select aria-label="Correct ${f}">${options(f, m.fix[f] || "")}</select></div>
    </div>`).join("");
  $("codes").querySelectorAll(".code").forEach(el => {
    const f = el.dataset.f;
    el.querySelector("button").onclick = () => toggle(f);
    el.querySelector("select").onchange = e => { mark(r).fix[f] = e.target.value; save(); };
  });
  $("note").value = m.note;
  $("next").textContent = state.i === D.rows.length - 1 ? "Correct as marked, finish" : "Correct as marked, next";
  $("prev").disabled = state.i === 0;
}
function toggle(f) { const m = mark(D.rows[state.i]); m.wrong[f] = !m.wrong[f]; if (!m.wrong[f]) delete m.fix[f]; save(); render(); }
function go(d) {
  const m = mark(D.rows[state.i]);
  if (d > 0) m.seen = true;
  m.note = $("note").value;
  state.i = Math.max(0, Math.min(D.rows.length - 1, state.i + d));
  save(); render();
  if (d > 0 && D.rows.every(x => state.marks[x.key] && state.marks[x.key].seen)) $("status").textContent = "All events checked. Download the result.";
}
$("next").onclick = () => go(1);
$("prev").onclick = () => go(-1);
$("note").oninput = e => { mark(D.rows[state.i]).note = e.target.value; save(); };
$("first-open").onclick = () => { const k = D.rows.findIndex(x => !(state.marks[x.key] && state.marks[x.key].seen)); if (k >= 0) { state.i = k; save(); render(); } };
document.addEventListener("keydown", e => {
  if (e.target.matches("textarea, select, input")) return;
  if (["1", "2", "3"].includes(e.key)) { toggle(FIELDS[+e.key - 1]); e.preventDefault(); }
  else if (e.key === "Enter" || e.key === "ArrowRight") { if (e.target.tagName !== "BUTTON" || e.key === "ArrowRight") { go(1); e.preventDefault(); } }
  else if (e.key === "ArrowLeft") { go(-1); e.preventDefault(); }
});

const COLS = ["year", "event", "detail", "theme", "valence", "anchor", "theme_ok", "valence_ok", "anchor_ok",
  "theme_fix", "valence_fix", "anchor_fix", "note", "model", "run", "order"];
const cell = v => /[",\n\r]/.test(v) ? `"${String(v).replace(/"/g, '""')}"` : String(v);
$("download").onclick = () => {
  mark(D.rows[state.i]).note = $("note").value; save();
  const lines = [COLS.join(",")];
  for (const r of D.rows) {
    const m = state.marks[r.key], seen = m && m.seen, [model, run, order] = r.key.split("|");
    const v = { ...r, model, run, order, note: m ? m.note : "" };
    for (const f of FIELDS) { v[f + "_ok"] = seen ? (m.wrong[f] ? "n" : "y") : ""; v[f + "_fix"] = m && m.wrong[f] ? (m.fix[f] || "") : ""; }
    lines.push(COLS.map(c => cell(v[c] ?? "")).join(","));
  }
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([lines.join("\n") + "\n"], { type: "text/csv" }));
  a.download = "handcheck-result.csv"; a.click();
  $("status").textContent = "Saved handcheck-result.csv to your downloads.";
};
function parseCSV(t) {
  const out = []; let row = [], f = "", q = false;
  for (let i = 0; i < t.length; i++) {
    const c = t[i];
    if (q) { if (c === '"') { if (t[i + 1] === '"') { f += '"'; i++; } else q = false; } else f += c; }
    else if (c === '"') q = true; else if (c === ",") { row.push(f); f = ""; }
    else if (c === "\n" || c === "\r") { if (c === "\r" && t[i + 1] === "\n") i++; row.push(f); out.push(row); row = []; f = ""; }
    else f += c;
  }
  if (f || row.length) { row.push(f); out.push(row); }
  return out;
}
$("load").onchange = async e => {
  const file = e.target.files[0]; if (!file) return;
  const [head, ...rows] = parseCSV(await file.text()); let n = 0;
  for (const cells of rows) {
    const v = Object.fromEntries(head.map((h, k) => [h, cells[k] || ""]));
    if (!["y", "n"].includes(v.theme_ok)) continue;
    const m = { seen: true, wrong: {}, fix: {}, note: v.note || "" };
    for (const f of FIELDS) if (v[f + "_ok"] === "n") { m.wrong[f] = true; if (v[f + "_fix"]) m.fix[f] = v[f + "_fix"]; }
    state.marks[`${v.model}|${v.run}|${v.order}`] = m; n++;
  }
  save(); render(); $("status").textContent = `Loaded ${n} checked events.`;
};
render();
</script>
</body>
</html>
"""


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--score", type=Path, help="a result file from the page")
    a = p.parse_args()
    score(a.score) if a.score else page()
