"""Analyse the anchor forecasts: agreement within and between models, and change by era.

Usage:
    uv run scripts/parse.py
    uv run scripts/analyse_anchors.py

Reads data/parsed/anchors.csv and data/parsed/runs.csv. Writes data/analysis/:
    anchors_model_event.csv  one row per model and anchor (summary over runs)
    anchors_event.csv        one row per anchor (summary over models, one vote per model)
    anchors_model.csv        one row per model (assumed present, indices)
    anchors_summary.md       the main numbers in plain text

Conventions
- "never" is a null year: the model thinks it will not happen before 10000.
  For medians and ranks, never counts as later than any year.
- Horizon is the forecast year minus the year the model believes it is now
  (current_year in the same run), at least 1. Spreads use log10 of the horizon,
  because a 10-year gap in 2040 and a 1,000-year gap in 5000 are alike on this scale.
- Between-model summaries use the median of each model, so each model has one vote,
  whatever its number of valid runs.
"""

import csv
import math
import statistics as st
import tomllib
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PARSED = ROOT / "data" / "parsed"
OUT = ROOT / "data" / "analysis"
NEVER = math.inf

# Index groups. Each index is the mean probability (before 10000) of its anchors.
INDICES = {
    "catastrophe": ["extinction", "nuclear_war", "pandemic_10pct", "famine_10m",
                    "civilisation_collapse", "democracy_end"],
    "technology": ["agi", "fusion_grid", "mind_upload", "ageing_stopped", "kardashev_1",
                   "interstellar_probe", "interstellar_settlement", "orbital_10k", "mars_landing"],
    "ai_takeover": ["ai_succession"],
}

# ---------------------------------------------------------------- helpers


def num(v: str):
    return None if v in ("", None) else float(v)


def median_year(years: list[float]) -> float | None:
    """Median with never as +inf. Returns inf when half or more of the runs say never."""
    if not years:
        return None
    return st.median(sorted(years))


def quantile(xs: list[float], p: float) -> float:
    """Inclusive (type 7) quantile of sorted xs. With never (inf) at a boundary,
    take the nearer value instead of interpolating to inf or NaN."""
    h = (len(xs) - 1) * p
    lo, hi = math.floor(h), math.ceil(h)
    a, b = xs[lo], xs[hi]
    if a == b:
        return a
    if math.isinf(a) or math.isinf(b):
        return b if h - lo >= 0.5 else a
    return a + (h - lo) * (b - a)


def quartiles(xs: list[float]) -> tuple[float | None, float | None]:
    xs = sorted(xs)
    if not xs:
        return None, None
    return quantile(xs, 0.25), quantile(xs, 0.75)


def iqr(xs: list[float]) -> float | None:
    q1, q3 = quartiles(xs)
    if q1 is None or math.isinf(q1) or math.isinf(q3):
        return None
    return q3 - q1


def log_h(year: float, current: float | None) -> float | None:
    if year is None or math.isinf(year) or current is None:
        return None
    return math.log10(max(year - current, 1))


def fmt_year(y) -> str:
    if y is None:
        return ""
    if math.isinf(y):
        return "never"
    return str(int(round(y)))


def r(x, d=3):
    return "" if x is None else round(x, d)


def ranks(values: list[float]) -> list[float]:
    """Average ranks, ties shared (inf ties with inf)."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    out = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        for k in range(i, j + 1):
            out[order[k]] = (i + j) / 2 + 1
        i = j + 1
    return out


def spearman(x: list[float], y: list[float]) -> float | None:
    if len(x) < 3:
        return None
    rx, ry = ranks(x), ranks(y)
    try:
        return st.correlation(rx, ry)
    except st.StatisticsError:
        return None


def kendall_w(table: dict[str, dict[str, float]], items: list[str]) -> float | None:
    """Kendall's W, with tie correction. table: rater -> item -> value. Complete raters only."""
    raters = [m for m, row in table.items() if all(row.get(i) is not None for i in items)]
    m, n = len(raters), len(items)
    if m < 2 or n < 2:
        return None
    sums = [0.0] * n
    ties = 0.0
    for rater in raters:
        vals = [table[rater][i] for i in items]
        rk = ranks(vals)
        for k in range(n):
            sums[k] += rk[k]
        for v in set(vals):
            t = vals.count(v)
            ties += t ** 3 - t
    mean = m * (n + 1) / 2
    s = sum((x - mean) ** 2 for x in sums)
    denom = m ** 2 * (n ** 3 - n) - m * ties
    return 12 * s / denom if denom else None


def icc1(groups: dict[str, list[float]]) -> float | None:
    """One-way random-effects ICC(1) for unequal group sizes.

    Share of the variance in single runs that comes from the model.
    """
    groups = {k: v for k, v in groups.items() if v}
    a = len(groups)
    n_total = sum(len(v) for v in groups.values())
    if a < 2 or n_total - a < 1:
        return None
    grand = sum(sum(v) for v in groups.values()) / n_total
    msb = sum(len(v) * (st.fmean(v) - grand) ** 2 for v in groups.values()) / (a - 1)
    msw = sum(sum((x - st.fmean(v)) ** 2 for x in v) for v in groups.values()) / (n_total - a)
    k0 = (n_total - sum(len(v) ** 2 for v in groups.values()) / n_total) / (a - 1)
    denom = msb + (k0 - 1) * msw
    return (msb - msw) / denom if denom else None


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("")
        return
    with path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


# ---------------------------------------------------------------- load


def load():
    cfg = tomllib.loads((ROOT / "config.toml").read_text())
    anchor_ids = [a["id"] for a in cfg["anchors"]]
    eras = {m["id"]: m["era"] for m in cfg["models"]}
    model_order = [m["id"] for m in cfg["models"]]

    runs = list(csv.DictReader((PARSED / "runs.csv").open()))
    good = {(x["model"], x["run"]) for x in runs
            if x["prompt"] == "anchors" and x["status"] in ("ok", "partial")}
    current = {(x["model"], x["run"]): num(x["current_year"])
               for x in runs if x["prompt"] == "anchors"}
    present_all = defaultdict(list)  # assumed present, both prompts
    for x in runs:
        if num(x["current_year"]) is not None:
            present_all[x["model"]].append(num(x["current_year"]))

    # data[model][anchor] = list of (year or inf, probability or None, horizon log or None, past)
    data = defaultdict(lambda: defaultdict(list))
    for x in csv.DictReader((PARSED / "anchors.csv").open()):
        key = (x["model"], x["run"])
        if key not in good or x["status"] != "ok":
            continue
        year = num(x["year"])
        y = NEVER if year is None else year
        data[x["model"]][x["id"]].append({
            "year": y,
            "prob": num(x["probability"]),
            "logh": log_h(y, current.get(key)),
            "past": x["past"] == "True",
        })
    models = [m for m in model_order if m in data]
    return anchor_ids, eras, models, data, present_all


# ---------------------------------------------------------------- analysis


def main() -> None:
    anchor_ids, eras, models, data, present_all = load()
    OUT.mkdir(parents=True, exist_ok=True)

    # Model x anchor
    me_rows = []
    med = defaultdict(dict)       # model -> anchor -> median year (inf = never)
    med_prob = defaultdict(dict)  # model -> anchor -> median probability
    med_logh = defaultdict(dict)  # model -> anchor -> median log horizon (finite only)
    for m in models:
        for a in anchor_ids:
            obs = data[m].get(a, [])
            if not obs:
                continue
            # A past year answers a different question (the first time ever), so it
            # stays out of the year statistics. share_past counts it.
            years = [o["year"] for o in obs if not o["past"]]
            probs = [o["prob"] for o in obs if o["prob"] is not None]
            loghs = [o["logh"] for o in obs if o["logh"] is not None and not o["past"]]
            if not years:
                continue
            my = median_year(years)
            mp = st.median(probs) if probs else None
            med[m][a] = my
            med_prob[m][a] = mp
            if loghs and not math.isinf(my):
                med_logh[m][a] = st.median(loghs)
            q1, q3 = quartiles(years)
            p1, p3 = quartiles(probs)
            me_rows.append({
                "model": m, "era": eras[m], "anchor": a, "n_runs": len(obs),
                "median_year": fmt_year(my), "q1_year": fmt_year(q1), "q3_year": fmt_year(q3),
                "share_never": r(sum(math.isinf(y) for y in years) / len(years)),
                "share_past": r(sum(o["past"] for o in obs) / len(obs)),
                "median_prob": r(mp), "q1_prob": r(p1), "q3_prob": r(p3),
                "iqr_log_horizon": r(iqr(loghs)),
            })
    write_csv(OUT / "anchors_model_event.csv", me_rows)

    # Anchor across models (one vote per model)
    ev_rows = []
    for a in anchor_ids:
        ms = [m for m in models if a in med[m]]
        if not ms:
            continue
        years = [med[m][a] for m in ms]
        probs = [med_prob[m][a] for m in ms if med_prob[m][a] is not None]
        between_logh = [med_logh[m][a] for m in ms if a in med_logh[m]]
        within = [iqr([o["logh"] for o in data[m][a] if o["logh"] is not None]) for m in ms]
        within = [w for w in within if w is not None]
        q1, q3 = quartiles(years)
        lo = min(years)
        hi = max(years)
        icc_p = icc1({m: [o["prob"] for o in data[m][a] if o["prob"] is not None] for m in ms})
        era_probs = defaultdict(list)
        for m in ms:
            if med_prob[m][a] is not None:
                era_probs[eras[m]].append(med_prob[m][a])
        rho = spearman([eras[m] for m in ms if med_prob[m][a] is not None], probs)
        row = {
            "anchor": a, "n_models": len(ms),
            "median_year": fmt_year(median_year(years)),
            "q1_year": fmt_year(q1), "q3_year": fmt_year(q3),
            "earliest": fmt_year(lo), "latest": fmt_year(hi),
            "models_never": sum(math.isinf(y) for y in years),
            "median_prob": r(st.median(probs) if probs else None),
            "sd_prob_between": r(st.pstdev(probs) if len(probs) > 1 else None),
            "min_prob": r(min(probs) if probs else None),
            "max_prob": r(max(probs) if probs else None),
            # Needs 3 models with a date, and most models with a date; else it says nothing.
            "between_iqr_log_horizon": r(iqr(between_logh))
            if len(between_logh) >= 3 and len(between_logh) * 2 > len(ms) else "",
            "within_iqr_log_horizon": r(st.median(within) if within else None),
            "icc_prob": r(icc_p),
            "spearman_era_prob": r(rho),
        }
        for e in sorted(era_probs):
            row[f"prob_{e}"] = r(st.median(era_probs[e]))
        ev_rows.append(row)
    # Same columns in every row, for the CSV.
    era_cols = sorted({k for row in ev_rows for k in row if k.startswith("prob_")})
    for row in ev_rows:
        for c in era_cols:
            row.setdefault(c, "")
    write_csv(OUT / "anchors_event.csv", ev_rows)

    # Model level
    md_rows = []
    for m in models:
        row = {
            "model": m, "era": eras[m],
            "n_runs": max((len(v) for v in data[m].values()), default=0),
            "assumed_present": fmt_year(st.median(present_all[m])) if present_all[m] else "",
            "present_min": fmt_year(min(present_all[m])) if present_all[m] else "",
            "present_max": fmt_year(max(present_all[m])) if present_all[m] else "",
        }
        for name, ids in INDICES.items():
            vals = [med_prob[m][a] for a in ids if med_prob[m].get(a) is not None]
            row[f"index_{name}"] = r(st.fmean(vals) if len(vals) == len(ids) else None)
        # General level of probability, to separate pessimism from a habit of giving
        # high probabilities to everything.
        rest = [a for a in anchor_ids if a not in INDICES["catastrophe"]]
        vals_all = [med_prob[m].get(a) for a in anchor_ids]
        vals_rest = [med_prob[m].get(a) for a in rest]
        row["index_all"] = r(st.fmean(vals_all) if None not in vals_all else None)
        row["index_non_catastrophe"] = r(st.fmean(vals_rest) if None not in vals_rest else None)
        if row["index_catastrophe"] != "" and row["index_non_catastrophe"] != "":
            row["catastrophe_minus_rest"] = r(row["index_catastrophe"] - row["index_non_catastrophe"])
        else:
            row["catastrophe_minus_rest"] = ""
        row["share_never"] = r(st.fmean(math.isinf(med[m][a]) for a in med[m]))
        md_rows.append(row)

    # Residual of the catastrophe index after the general level (OLS on the
    # non-catastrophe index, across models). Positive = more pessimistic than
    # the model's general level predicts.
    pairs = [(x["index_non_catastrophe"], x["index_catastrophe"]) for x in md_rows
             if x["index_non_catastrophe"] != "" and x["index_catastrophe"] != ""]
    slope = intercept = None
    if len(pairs) >= 3:
        slope, intercept = st.linear_regression([p[0] for p in pairs], [p[1] for p in pairs])
    for x in md_rows:
        if slope is not None and x["index_non_catastrophe"] != "" and x["index_catastrophe"] != "":
            x["catastrophe_residual"] = r(x["index_catastrophe"] - (intercept + slope * x["index_non_catastrophe"]))
        else:
            x["catastrophe_residual"] = ""
    write_csv(OUT / "anchors_model.csv", md_rows)
    level_fit = (slope, intercept, st.correlation([p[0] for p in pairs], [p[1] for p in pairs])
                 if len(pairs) >= 3 else None)

    # Rank agreement: Kendall's W over anchors, overall and by era
    w_all = kendall_w(med, anchor_ids)
    w_era = {e: kendall_w({m: med[m] for m in models if eras[m] == e}, anchor_ids)
             for e in sorted({eras[m] for m in models})}

    # Index trends by era
    trend = {}
    cols = [f"index_{n}" for n in INDICES] + ["index_all", "index_non_catastrophe",
                                              "catastrophe_minus_rest", "catastrophe_residual"]
    for name in cols:
        xs = [(eras[x["model"]], x[name]) for x in md_rows if x[name] != ""]
        trend[name] = (spearman([e for e, _ in xs], [v for _, v in xs]),
                       {e: st.median([v for ee, v in xs if ee == e])
                        for e in sorted({e for e, _ in xs})})

    write_summary(models, eras, md_rows, ev_rows, w_all, w_era, trend, level_fit)
    print((OUT / "anchors_summary.md").read_text())


def write_summary(models, eras, md_rows, ev_rows, w_all, w_era, trend, level_fit):
    L = ["# Anchors: summary", ""]
    n_by_era = defaultdict(int)
    for m in models:
        n_by_era[eras[m]] += 1
    L.append(f"Models: {len(models)} ({', '.join(f'{e}: {n}' for e, n in sorted(n_by_era.items()))}).")
    L.append("Generated by scripts/analyse_anchors.py. Do not edit.")
    L += ["", "## Do the models rank the events in the same order?", ""]
    L.append(f"Kendall's W over {len(ev_rows)} anchors (0 = no agreement, 1 = same order): "
             f"{r(w_all)} overall.")
    L.append("By era: " + ", ".join(f"{e} {r(w)}" for e, w in w_era.items()) + ".")
    L += ["", "## Assumed present", ""]
    L.append("| model | era | assumed year (median) | range |")
    L.append("|---|---|---|---|")
    for x in md_rows:
        L.append(f"| {x['model']} | {x['era']} | {x['assumed_present']} | "
                 f"{x['present_min']} to {x['present_max']} |")
    L += ["", "## Indices by era", "",
          "Mean probability before 10000 of the anchors in each group. Median over the models of an era.", ""]
    for name, (rho, by_era) in trend.items():
        L.append(f"- {name}: " + ", ".join(f"{e} {r(v, 2)}" for e, v in by_era.items())
                 + f" (Spearman with era {r(rho, 2)})")
    slope, intercept, corr = level_fit
    if slope is not None:
        L += ["", "Pessimism or general level? Across models, the catastrophe index against the "
              f"non-catastrophe index: Pearson r {r(corr, 2)}, slope {r(slope, 2)}. "
              "catastrophe_residual is what is left after the general level."]
        L += ["", "| model | era | catastrophe | non-catastrophe | difference | residual |",
              "|---|---|---|---|---|---|"]
        for x in sorted(md_rows, key=lambda x: -(x["catastrophe_residual"] or 0)):
            L.append(f"| {x['model']} | {x['era']} | {x['index_catastrophe']} | "
                     f"{x['index_non_catastrophe']} | {x['catastrophe_minus_rest']} | "
                     f"{x['catastrophe_residual']} |")
    L += ["", "## Events: most and least agreement on the date", "",
          "Between-model IQR of log10 years from the present. Small = models agree.", ""]
    ranked = sorted((x for x in ev_rows if x["between_iqr_log_horizon"] != ""),
                    key=lambda x: x["between_iqr_log_horizon"])
    L.append("| anchor | median year | IQR of model medians | models saying never | log IQR between | log IQR within |")
    L.append("|---|---|---|---|---|---|")
    for x in ranked:
        L.append(f"| {x['anchor']} | {x['median_year']} | {x['q1_year']} to {x['q3_year']} | "
                 f"{x['models_never']}/{x['n_models']} | {x['between_iqr_log_horizon']} | "
                 f"{x['within_iqr_log_horizon']} |")
    rest = [x for x in ev_rows if x["between_iqr_log_horizon"] == ""]
    if rest:
        L += ["", "Not ranked, because half or more of the models say never (or fewer than 3 give a date):", ""]
        for x in rest:
            L.append(f"- {x['anchor']}: never for {x['models_never']}/{x['n_models']} models; "
                     f"dates from {x['earliest']} to {x['latest']}")
    L += ["", "## Events: probability before 10000", "",
          "ICC: share of the run-to-run variance that comes from the model (0 = models alike).", ""]
    L.append("SD between models: population SD of the 24 model medians.")
    L.append("")
    L.append("| anchor | median prob | SD between models | min | max | ICC | Spearman with era |")
    L.append("|---|---|---|---|---|---|---|")
    for x in sorted(ev_rows, key=lambda x: -(x["median_prob"] or 0)):
        L.append(f"| {x['anchor']} | {x['median_prob']} | {x['sd_prob_between']} | {x['min_prob']} | {x['max_prob']} | "
                 f"{x['icc_prob']} | {x['spearman_era_prob']} |")
    cat = INDICES["catastrophe"]
    sd_c = [x["sd_prob_between"] for x in ev_rows if x["anchor"] in cat and x["sd_prob_between"] != ""]
    sd_o = [x["sd_prob_between"] for x in ev_rows if x["anchor"] not in cat and x["sd_prob_between"] != ""]
    L += ["", f"Mean SD between models: catastrophe anchors {r(st.fmean(sd_c))}, other anchors {r(st.fmean(sd_o))}."]
    icc = [x["icc_prob"] for x in ev_rows if x["icc_prob"] != ""]
    L.append(f"ICC: from {min(icc)} to {max(icc)}, median {r(st.median(icc))}; above 0.4 for {sum(v > 0.4 for v in icc)} of {len(icc)} anchors.")
    (OUT / "anchors_summary.md").write_text("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
