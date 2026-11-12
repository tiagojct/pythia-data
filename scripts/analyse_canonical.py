"""Analyse the canonical events and write the material for each horizon chapter.

Usage:
    uv run scripts/analyse_canonical.py

Reads data/parsed/, data/coded/canonical_codes.csv, data/coded/codes_<coder>.csv and
coding/canonical.json. Writes data/analysis/:
    canonical_events.csv  one row per canonical event: models, runs, median year, era mix, valence
    canonical_model.csv   one row per model: originality (share of events outside the canonical list)
    chapters.md           per horizon: the shared events, and candidate quotes from events no other model wrote

Each model has one vote. A model "uses" a canonical event when at least one of its runs has it.
"""

import csv
import json
import random
import statistics as st
import tomllib
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PARSED = ROOT / "data" / "parsed"
CODED = ROOT / "data" / "coded"
OUT = ROOT / "data" / "analysis"
SEED = 20261113
CHAPTERS = [("Now to 2030", 2030), ("2031 to 2050", 2050), ("2051 to 2100", 2100), ("2101 to 2200", 2200),
            ("2201 to 2500", 2500), ("2501 to 3000", 3000), ("3001 to 5000", 5000), ("5001 to 10000", 10_000)]


def chapter(y: float) -> str:
    for name, top in CHAPTERS:
        if y <= top:
            return name
    return CHAPTERS[-1][0]


def spearman(x, y):
    def rk(v):
        o = sorted(range(len(v)), key=lambda i: v[i])
        out = [0.0] * len(v)
        i = 0
        while i < len(o):
            j = i
            while j + 1 < len(o) and v[o[j + 1]] == v[o[i]]:
                j += 1
            for k in range(i, j + 1):
                out[o[k]] = (i + j) / 2 + 1
            i = j + 1
        return out
    try:
        return st.correlation(rk(x), rk(y))
    except st.StatisticsError:
        return None


def write_csv(path, rows):
    with path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def short(m):
    return m.split("/", 1)[1]


def main() -> None:
    cfg = tomllib.loads((ROOT / "config.toml").read_text())
    eras = {m["id"]: m["era"] for m in cfg["models"]}
    order = [m["id"] for m in cfg["models"]]
    canon = {c["id"]: c for c in json.loads((ROOT / "coding" / "canonical.json").read_text())["canonical"]}

    runs = [x for x in csv.DictReader((PARSED / "runs.csv").open())
            if x["prompt"] == "timeline" and x["status"] == "ok"]
    good = {(x["model"], x["run"]) for x in runs}
    runs_per_model = Counter(x["model"] for x in runs)
    cc = {(r["model"], r["run"], r["order"]): r["canonical"] for r in csv.DictReader((CODED / "canonical_codes.csv").open())}
    tc = {(r["model"], r["run"], r["order"]): r for r in
          csv.DictReader((CODED / "codes_anthropic__claude-haiku-5.5.csv").open())}

    events = []
    for e in csv.DictReader((PARSED / "timeline_events.csv").open()):
        k = (e["model"], e["run"], e["order"])
        if (e["model"], e["run"]) not in good or not e["year"] or not cc.get(k):
            continue
        events.append({**e, "year": int(e["year"]), "canonical": cc[k],
                       "valence": tc.get(k, {}).get("valence", ""), "theme": tc.get(k, {}).get("theme", "")})
    models = [m for m in order if runs_per_model[m]]

    # Canonical events
    by_canon = defaultdict(lambda: defaultdict(list))  # id -> model -> events
    for e in events:
        if e["canonical"] != "other":
            by_canon[e["canonical"]][e["model"]].append(e)
    canon_rows = []
    for cid, c in canon.items():
        per_model = by_canon.get(cid, {})
        if not per_model:
            canon_rows.append({"id": cid, "label": c["label"], "models": 0, "share_runs": 0.0,
                               "median_year": "", "q1_year": "", "q3_year": "", "chapter": "",
                               "models_2023": 0, "models_2024": 0, "models_2025": 0, "models_2026": 0,
                               "share_negative": ""})
            continue
        model_years = sorted(st.median(e["year"] for e in ev) for ev in per_model.values())
        med = st.median(model_years)
        q = st.quantiles(model_years, n=4, method="inclusive") if len(model_years) > 1 else [med, med, med]
        share_runs = st.fmean(len({e["run"] for e in per_model.get(m, [])}) / runs_per_model[m] for m in models)
        allev = [e for ev in per_model.values() for e in ev]
        row = {"id": cid, "label": c["label"], "models": len(per_model), "share_runs": round(share_runs, 3),
               "median_year": round(med), "q1_year": round(q[0]), "q3_year": round(q[2]), "chapter": chapter(med)}
        for era in (2023, 2024, 2025, 2026):
            row[f"models_{era}"] = sum(1 for m in per_model if eras[m] == era)
        row["share_negative"] = round(sum(e["valence"] == "negative" for e in allev) / len(allev), 2)
        canon_rows.append(row)
    canon_rows.sort(key=lambda r: (-r["models"], -r["share_runs"]))
    write_csv(OUT / "canonical_events.csv", canon_rows)

    # Originality by model
    model_rows = []
    use = {m: {cid for cid, pm in by_canon.items() if m in pm} for m in models}
    n_models_using = {cid: len(pm) for cid, pm in by_canon.items()}
    for m in models:
        ev = [e for e in events if e["model"] == m]
        other = sum(e["canonical"] == "other" for e in ev) / len(ev)
        # Rarity: mean, over the model's canonical events, of the share of OTHER models that do not use it.
        rar = [1 - (n_models_using[e["canonical"]] - 1) / (len(models) - 1) for e in ev if e["canonical"] != "other"]
        model_rows.append({"model": m, "era": eras[m], "events": len(ev), "share_other": round(other, 3),
                           "canonical_used": len(use[m]), "rarity_of_canonical": round(st.fmean(rar), 3) if rar else ""})
    write_csv(OUT / "canonical_model.csv", model_rows)

    # Chapters
    rng = random.Random(SEED)
    L = ["# Chapter material", "", "Generated by scripts/analyse_canonical.py. Do not edit.", "",
         f"{len(events)} events, {len(canon)} canonical events, {len(models)} models.",
         f"Events outside the canonical list: {sum(e['canonical'] == 'other' for e in events) / len(events):.0%}.", ""]
    rho = spearman([r["era"] for r in model_rows], [r["share_other"] for r in model_rows])
    L += ["## Originality", "",
          f"Share of each model's events that are not canonical. Spearman with era: {rho:.2f}.", "",
          "| model | era | share not canonical | canonical events used |", "|---|---|---|---|"]
    for r in sorted(model_rows, key=lambda r: -r["share_other"]):
        L.append(f"| {short(r['model'])} | {r['era']} | {r['share_other']:.0%} | {r['canonical_used']} |")

    for name, _ in CHAPTERS:
        rows_c = [r for r in canon_rows if r["chapter"] == name]
        L += ["", f"## {name}", "", "Shared events (median year of the models that use it; models out of 24):", ""]
        for r in sorted(rows_c, key=lambda r: -r["models"])[:14]:
            L.append(f"- {r['label']}: {r['median_year']} ({r['q1_year']} to {r['q3_year']}), "
                     f"{r['models']} models, negative {r['share_negative']:.0%}")
        lo = 0 if name == CHAPTERS[0][0] else dict(CHAPTERS)[CHAPTERS[[c[0] for c in CHAPTERS].index(name) - 1][0]] + 1
        hi = dict(CHAPTERS)[name]
        pool = [e for e in events if e["canonical"] == "other" and lo <= e["year"] <= hi and len(e["event"]) > 30]
        rng.shuffle(pool)
        picked, seen = [], set()
        for e in pool:
            if e["model"] in seen:
                continue
            picked.append(e)
            seen.add(e["model"])
            if len(picked) == 8:
                break
        L += ["", "Events that no canonical event covers (candidate quotes, one per model):", ""]
        for e in sorted(picked, key=lambda e: e["year"]):
            L.append(f"- {e['year']}, {short(e['model'])}: \"{e['event']}\"" + (f" {e['detail']}" if e["detail"] else ""))

    L += ["", "## Endings", "", "The summary of the first valid run of each model.", ""]
    for m in models:
        r = next((x for x in sorted(runs, key=lambda x: int(x["run"])) if x["model"] == m and x["summary"]), None)
        if r:
            L.append(f"- {short(m)} ({eras[m]}), humanity in 10000: {r['humanity_10000']}. \"{r['summary']}\"")
    (OUT / "chapters.md").write_text("\n".join(L) + "\n")

    print(f"canonical events used by 12 or more models: {sum(r['models'] >= 12 for r in canon_rows)}")
    print("top 15:")
    for r in canon_rows[:15]:
        print(f"  {r['models']:2} models  {r['median_year']}  {r['label']}")
    print("\n".join(L[7:7 + 4 + len(model_rows)]))


if __name__ == "__main__":
    main()
