"""Analyse the coded timelines: themes, valence and agreement by model, era and horizon.

Usage:
    uv run scripts/analyse_timeline.py

Reads data/parsed/ and data/coded/codes_anthropic__claude-haiku-5.5.csv.
Writes data/analysis/:
    timeline_model.csv     one row per model: event counts, negative share, theme shares
    timeline_horizon.csv   one row per horizon: theme shares and negative share
    timeline_summary.md    the main numbers in plain text

Each model has one vote: shares are computed per model, then averaged.
"""

import csv
import math
import statistics as st
import tomllib
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PARSED = ROOT / "data" / "parsed"
CODES = ROOT / "data" / "coded" / "codes_anthropic__claude-haiku-5.5.csv"
OUT = ROOT / "data" / "analysis"

# Horizons follow the planned chapters. Upper bounds, inclusive.
HORIZONS = [("to 2030", 2030), ("2031-2050", 2050), ("2051-2100", 2100), ("2101-2200", 2200),
            ("2201-2500", 2500), ("2501-3000", 3000), ("3001-5000", 5000), ("5001-10000", 10_000)]


def horizon(year: int) -> str | None:
    for name, top in HORIZONS:
        if year <= top:
            return name
    return None


def spearman(x, y):
    def ranks(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        out = [0.0] * len(v)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
                j += 1
            for k in range(i, j + 1):
                out[order[k]] = (i + j) / 2 + 1
            i = j + 1
        return out
    try:
        return st.correlation(ranks(x), ranks(y))
    except st.StatisticsError:
        return None


def js_similarity(p: dict, q: dict) -> float:
    """1 minus the Jensen-Shannon divergence (base 2) of two distributions."""
    keys = set(p) | set(q)
    m = {k: (p.get(k, 0) + q.get(k, 0)) / 2 for k in keys}

    def kl(a):
        return sum(a[k] * math.log2(a[k] / m[k]) for k in keys if a.get(k, 0) > 0)
    return 1 - (kl(p) + kl(q)) / 2


def r(x, d=3):
    return "" if x is None else round(x, d)


def write_csv(path, rows):
    cols = list(dict.fromkeys(k for row in rows for k in row))
    with path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, restval="")
        w.writeheader()
        w.writerows(rows)


def main() -> None:
    cfg = tomllib.loads((ROOT / "config.toml").read_text())
    eras = {m["id"]: m["era"] for m in cfg["models"]}
    order = [m["id"] for m in cfg["models"]]

    runs = [x for x in csv.DictReader((PARSED / "runs.csv").open())
            if x["prompt"] == "timeline" and x["status"] == "ok"]
    good = {(x["model"], x["run"]) for x in runs}
    present = {(x["model"], x["run"]): int(x["current_year"]) if x["current_year"] else None for x in runs}
    codes = {(c["model"], c["run"], c["order"]): c for c in csv.DictReader(CODES.open())}

    events = []
    for e in csv.DictReader((PARSED / "timeline_events.csv").open()):
        if (e["model"], e["run"]) not in good or not e["year"]:
            continue
        c = codes.get((e["model"], e["run"], e["order"]))
        if not c or c["flag"]:
            continue
        y = int(e["year"])
        cy = present[(e["model"], e["run"])]
        events.append({**e, "year": y, "theme": c["theme"], "valence": c["valence"],
                       "anchor": c["anchor"], "horizon": horizon(y),
                       "before_present": cy is not None and y < cy})
    themes = sorted({e["theme"] for e in events})
    models = [m for m in order if any(e["model"] == m for e in events)]

    # Model level
    by_model = defaultdict(list)
    for e in events:
        by_model[e["model"]].append(e)
    runs_by_model = defaultdict(list)
    for x in runs:
        runs_by_model[x["model"]].append(x)

    model_rows, theme_dist = [], {}
    for m in models:
        ev = by_model[m]
        n = len(ev)
        tc = Counter(e["theme"] for e in ev)
        theme_dist[m] = {t: tc[t] / n for t in tc}
        vc = Counter(e["valence"] for e in ev)
        h10k = Counter(x["humanity_10000"] for x in runs_by_model[m])
        n_runs = len(runs_by_model[m])
        far = [e for e in ev if e["year"] > 3000]
        row = {
            "model": m, "era": eras[m], "runs": n_runs,
            "events_per_run": r(n / n_runs, 1),
            "share_negative": r(vc["negative"] / n),
            "share_positive": r(vc["positive"] / n),
            "share_after_3000": r(len(far) / n),
            "negative_after_3000": r(sum(e["valence"] == "negative" for e in far) / len(far)) if far else "",
            "humanity_yes": h10k["yes"], "humanity_uncertain": h10k["uncertain"], "humanity_no": h10k["no"],
            "share_before_present": r(sum(e["before_present"] for e in ev) / n),
        }
        for t in themes:
            row[f"theme_{t}"] = r(theme_dist[m].get(t, 0))
        model_rows.append(row)
    write_csv(OUT / "timeline_model.csv", model_rows)

    # Horizon level: theme shares, one vote per model
    hz_rows = []
    for name, _ in HORIZONS:
        per_model = []
        for m in models:
            ev = [e for e in by_model[m] if e["horizon"] == name]
            if ev:
                per_model.append((m, ev))
        if not per_model:
            continue
        row = {"horizon": name, "models": len(per_model),
               "events_per_run": r(st.fmean(len(ev) / len(runs_by_model[m]) for m, ev in per_model), 2),
               "share_negative": r(st.fmean(sum(e["valence"] == "negative" for e in ev) / len(ev)
                                            for m, ev in per_model))}
        # Theme agreement inside the horizon: mean pairwise JS similarity between models
        dists = {}
        for m, ev in per_model:
            tc = Counter(e["theme"] for e in ev)
            dists[m] = {t: tc[t] / len(ev) for t in tc}
        sims = [js_similarity(dists[a], dists[b]) for a, b in combinations(dists, 2)]
        row["similarity_between_models"] = r(st.fmean(sims)) if sims else ""
        for t in themes:
            row[f"theme_{t}"] = r(st.fmean(dists[m].get(t, 0) for m in dists))
        hz_rows.append(row)
    write_csv(OUT / "timeline_horizon.csv", hz_rows)

    # Free mentions of anchors: share of runs of each model that mention it
    anchor_ids = [a["id"] for a in cfg["anchors"]]
    mention = defaultdict(dict)
    for m in models:
        n_runs = len(runs_by_model[m])
        seen = defaultdict(set)
        for e in by_model[m]:
            if e["anchor"]:
                seen[e["anchor"]].add(e["run"])
        for a in anchor_ids:
            mention[a][m] = len(seen[a]) / n_runs

    write_summary(models, eras, model_rows, hz_rows, theme_dist, mention, anchor_ids, events)
    print((OUT / "timeline_summary.md").read_text())


def write_summary(models, eras, model_rows, hz_rows, theme_dist, mention, anchor_ids, events):
    L = ["# Timelines: summary", "", "Generated by scripts/analyse_timeline.py. Do not edit.", "",
         f"{len(events)} coded events from {len(models)} models."]

    def by_era(col):
        vals = defaultdict(list)
        for x in model_rows:
            if x[col] != "":
                vals[x["era"]].append(x[col])
        rho = spearman([x["era"] for x in model_rows if x[col] != ""],
                       [x[col] for x in model_rows if x[col] != ""])
        return ", ".join(f"{e} {r(st.median(v), 2)}" for e, v in sorted(vals.items())) + f" (Spearman with era {r(rho, 2)})"

    L += ["", "## By era (median over the models of an era)", ""]
    for col in ("events_per_run", "share_negative", "share_positive", "share_after_3000",
                "negative_after_3000", "share_before_present"):
        L.append(f"- {col}: {by_era(col)}")

    # Is the negative share only a result of longer timelines?
    era_v = [x["era"] for x in model_rows]
    neg_v = [x["share_negative"] for x in model_rows]
    len_v = [x["events_per_run"] for x in model_rows]
    r_en, r_el, r_nl = spearman(era_v, neg_v), spearman(era_v, len_v), spearman(neg_v, len_v)
    partial = (r_en - r_el * r_nl) / math.sqrt((1 - r_el ** 2) * (1 - r_nl ** 2))
    runs = defaultdict(list)
    for e in events:
        runs[(e["model"], e["run"])].append(e["valence"] == "negative")
    within = []
    for m in models:
        pairs = [(len(v), sum(v) / len(v)) for (mm, _), v in runs.items() if mm == m]
        if len({a for a, _ in pairs}) > 1 and len({b for _, b in pairs}) > 1:
            within.append(spearman([a for a, _ in pairs], [b for _, b in pairs]))
    L += ["", "Length check. Spearman across models: era and negative share "
          f"{r(r_en, 2)}, era and events per run {r(r_el, 2)}, negative share and events per run {r(r_nl, 2)}. "
          f"Partial correlation of era and negative share, controlling for events per run: {r(partial, 2)}. "
          f"Within each model, across its runs, Spearman of events per run and negative share: median "
          f"{r(st.median(within), 2)} over {len(within)} models, positive in {sum(w > 0 for w in within)}."]

    L += ["", "## Will humanity exist in 10000? (runs)", "", "| model | era | yes | uncertain | no |", "|---|---|---|---|---|"]
    for x in model_rows:
        L.append(f"| {x['model']} | {x['era']} | {x['humanity_yes']} | {x['humanity_uncertain']} | {x['humanity_no']} |")
    tot = Counter()
    for x in model_rows:
        for k in ("yes", "uncertain", "no"):
            tot[(x["era"], k)] += x[f"humanity_{k}"]
    L += ["", "By era: " + "; ".join(
        f"{e}: yes {tot[(e, 'yes')]}, uncertain {tot[(e, 'uncertain')]}, no {tot[(e, 'no')]}"
        for e in sorted({x['era'] for x in model_rows}))]

    L += ["", "## Do the models write about the same things?", "",
          "Mean pairwise similarity of the theme mix between models (1 minus Jensen-Shannon divergence; 1 = same mix)."]
    sims = [js_similarity(theme_dist[a], theme_dist[b]) for a, b in combinations(models, 2)]
    L.append(f"All horizons: {r(st.fmean(sims))}.")
    L += ["", "| horizon | events per run | negative share | similarity between models | top themes |", "|---|---|---|---|---|"]
    for h in hz_rows:
        top = sorted(((k[6:], v) for k, v in h.items() if k.startswith("theme_")), key=lambda kv: -kv[1])[:4]
        L.append(f"| {h['horizon']} | {h['events_per_run']} | {h['share_negative']} | {h["similarity_between_models"]} | "
                 + ", ".join(f"{t} {v:.2f}" for t, v in top) + " |")

    L += ["", "## Anchors mentioned without being asked", "",
          "Share of timeline runs that contain the anchor event. Median over models.", "",
          "| anchor | all | 2023 | 2024 | 2025 | 2026 |", "|---|---|---|---|---|---|"]
    rows = []
    for a in anchor_ids:
        vals = mention[a]
        era_med = {e: st.median([vals[m] for m in models if eras[m] == e]) for e in (2023, 2024, 2025, 2026)
                   if any(eras[m] == e for m in models)}
        rows.append((st.fmean(vals.values()), a, era_med))
    for mean, a, era_med in sorted(rows, reverse=True):
        L.append(f"| {a} | {r(mean, 2)} | " + " | ".join(str(r(era_med.get(e), 2)) for e in (2023, 2024, 2025, 2026)) + " |")
    (OUT / "timeline_summary.md").write_text("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
