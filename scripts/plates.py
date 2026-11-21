"""Draft plates for the essay, as one local HTML page with inline SVG.

Usage:
    uv run scripts/plates.py
    open plates/drafts.html

Reads data/analysis/*.csv. Writes plates/drafts.html. Hover a mark for its value;
each plate has a table view below it. Night palette: the plates are drawn on the dark
hall of the site (no card), with light ink and an era ramp that gets lighter with time.
"""

import csv
import html
import math
import tomllib
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AN = ROOT / "data" / "analysis"
OUT = ROOT / "plates"

# PAPER is the ground of the plates (the hall), and the ring colour around overlapping dots.
PAPER, INK, INK_SOFT, MUTE, RULE = "#0e0f11", "#e8ecee", "#c4c9cc", "#8b9196", "#2c2f34"
BAND = "#15171a"  # alternate rows
# Ordinal ramp for the dark ground: newer is lighter. All steps >= 3:1 on #0e0f11, about 1.5:1 apart.
ERA_COLOR = {2023: "#2d6bc0", 2024: "#3f8be6", 2025: "#79b0ef", 2026: "#c3dcfa"}
POS, NEG = "#3f8be6", "#e8693a"  # valence pair, validated for the dark ground (CVD dE 24.6)
NOW = 2026
PW = 780  # plate width in viewBox units; the site CSS sets the text at 15, 14 and 13 units
FONT = "'Source Serif 4', Charter, Georgia, serif"

LABELS = {
    "mars_landing": "A human walks on Mars", "orbital_10k": "10,000 people live off Earth",
    "interstellar_probe": "A probe reaches another star", "interstellar_settlement": "A planet of another star is settled",
    "et_contact": "Contact with alien intelligence", "fusion_grid": "Fusion power on the grid",
    "kardashev_1": "Kardashev Type I", "agi": "AGI", "ai_succession": "AI becomes the dominant intelligence",
    "mind_upload": "A mind is uploaded", "population_peak": "Population peaks",
    "lifespan_150": "Life expectancy above 150", "ageing_stopped": "Ageing is stopped",
    "engineered_majority": "Most newborns are gene-edited", "nuclear_war": "Nuclear war, 100 million dead",
    "pandemic_10pct": "Pandemic kills 10%", "warming_peak": "Warming peaks",
    "civilisation_collapse": "Civilisation collapses", "world_government": "World government",
    "extinction": "Humanity becomes extinct", "no_paid_work": "Paid work is optional",
    "english_science": "English loses science", "democracy_end": "No free elections anywhere",
    "religion_minority": "Religion becomes a minority", "wealth_top1_10pct": "Top 1% hold under 10% of wealth",
    "famine_10m": "Famine kills 10 million", "desalination_half": "Desalination gives half of water",
    "sea_level_1m": "Sea level +1 metre",
}


def rows(name):
    return list(csv.DictReader((AN / name).open()))


def esc(s) -> str:
    return html.escape(str(s), quote=True)


def short(model: str) -> str:
    return model.split("/", 1)[1]


def log_x(year: float, x0: float, x1: float) -> float:
    lo, hi = math.log10(1), math.log10(10_000 - NOW)
    v = math.log10(max(year - NOW, 1))
    return x0 + (v - lo) / (hi - lo) * (x1 - x0)


def legend_era(x: int, y: int) -> str:
    out = []
    for i, (era, col) in enumerate(ERA_COLOR.items()):
        out.append(f'<circle cx="{x + i * 112}" cy="{y}" r="5" fill="{col}"/>'
                   f'<text x="{x + i * 112 + 10}" y="{y + 4}" class="lab">{era} models</text>')
    return "".join(out)


def table(headers, body) -> str:
    th = "".join(f"<th>{esc(h)}</th>" for h in headers)
    tr = "".join("<tr>" + "".join(f"<td>{esc(c)}</td>" for c in row) + "</tr>" for row in body)
    return ('<details><summary>Table view</summary><div class="table-scroll" tabindex="0" role="region" aria-label="Data table">'
            f"<table><thead><tr>{th}</tr></thead><tbody>{tr}</tbody></table></div></details>")


# ---------------------------------------------------------------- plate 1


def plate_anchor_years() -> dict:
    me = rows("anchors_model_event.csv")
    ev = {r["anchor"]: r for r in rows("anchors_event.csv")}

    def sort_key(a):
        y = ev[a]["median_year"]
        return (1, 0) if y == "never" else (0, int(y))
    anchors = sorted(ev, key=sort_key)
    W, left, right_never = PW, 286, 70
    x0, x1 = left, W - right_never - 20
    row_h, top = 28, 70
    H = top + row_h * len(anchors) + 40
    era_off = {2023: -7.5, 2024: -2.5, 2025: 2.5, 2026: 7.5}
    s = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-labelledby="p1t">',
         '<title id="p1t">Forecast year of each anchor event, one dot per model</title>']
    s.append(legend_era(left, 18))
    for yr in (2030, 2050, 2100, 2200, 2500, 3000, 5000, 10000):
        x = log_x(yr, x0, x1)
        s.append(f'<line x1="{x:.1f}" y1="{top - 10}" x2="{x:.1f}" y2="{H - 34}" stroke="{RULE}"/>'
                 f'<text x="{x:.1f}" y="{H - 16}" class="tick" text-anchor="middle">{yr}</text>'
                 f'<text x="{x:.1f}" y="{top - 16}" class="tick" text-anchor="middle">{yr}</text>')
    xn = W - right_never + 10
    s.append(f'<text x="{xn + 20}" y="{H - 16}" class="tick" text-anchor="middle">never</text>'
             f'<line x1="{xn - 12}" y1="{top - 10}" x2="{xn - 12}" y2="{H - 34}" stroke="{RULE}" stroke-dasharray="2 3"/>')
    body = []
    for i, a in enumerate(anchors):
        cy = top + i * row_h + row_h / 2
        if i % 2 == 0:
            s.append(f'<rect x="0" y="{cy - row_h / 2}" width="{W}" height="{row_h}" fill="{BAND}"/>')
        s.append(f'<text x="{left - 14}" y="{cy + 4}" class="lab" text-anchor="end">{esc(LABELS.get(a, a))}</text>')
        nev = 0
        for r in (x for x in me if x["anchor"] == a):
            era = int(r["era"])
            tip = f'{short(r["model"])} ({era}): {r["median_year"]}'
            if r["median_year"] == "never":
                cx = xn + 4 + (nev % 6) * 7
                nev += 1
                s.append(f'<circle cx="{cx}" cy="{cy + era_off[era]:.1f}" r="3.5" fill="{ERA_COLOR[era]}" '
                         f'stroke="{PAPER}" stroke-width="1"><title>{esc(tip)}</title></circle>')
            else:
                cx = log_x(int(r["median_year"]), x0, x1)
                s.append(f'<circle cx="{cx:.1f}" cy="{cy + era_off[era]:.1f}" r="4.5" fill="{ERA_COLOR[era]}" '
                         f'stroke="{PAPER}" stroke-width="2"><title>{esc(tip)}</title></circle>')
        my = ev[a]["median_year"]
        if my != "never":
            mx = log_x(int(my), x0, x1)
            s.append(f'<line x1="{mx:.1f}" y1="{cy - 12}" x2="{mx:.1f}" y2="{cy + 12}" stroke="{INK}" stroke-width="2">'
                     f'<title>median of models: {my}</title></line>')
        body.append([LABELS.get(a, a), my, f'{ev[a]["q1_year"]} to {ev[a]["q3_year"]}',
                     f'{ev[a]["models_never"]}/{ev[a]["n_models"]}', ev[a]["median_prob"]])
    s.append("</svg>")
    return {"title": "When will it happen?",
            "caption": (            "<p>Median forecast year of each model for each anchor event (10 runs). Log scale from now. "
            "Black tick: median of the 24 models. Right column: models whose median is no date before 10000. "
            "In 183 of these 189 cases the same model gives the event a probability below one half: "
            "no date means unlikely, not impossible.</p>"),
            "svg": "".join(s), "table": table(["event", "median year", "IQR of model medians", "models: never", "median probability"], body)}


# ---------------------------------------------------------------- plate 2


def plate_present() -> dict:
    md = rows("anchors_model.csv")
    W, left = PW, 200
    x0, x1 = left, W - 40
    yr0, yr1 = 2022, 2027
    row_h, top = 24, 70
    H = top + row_h * len(md) + 40

    def X(y):
        return x0 + (y - yr0) / (yr1 - yr0) * (x1 - x0)
    s = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-labelledby="p2t">',
         '<title id="p2t">Year each model believes it is now</title>']
    s.append(legend_era(left, 20))
    s.append(f'<circle cx="{left}" cy="44" r="7" fill="none" stroke="{MUTE}" stroke-width="1.5"/>'
             f'<text x="{left + 14}" y="49" class="lab">ring: the model\'s release year group</text>')
    for y in range(yr0, yr1 + 1):
        s.append(f'<line x1="{X(y)}" y1="{top - 8}" x2="{X(y)}" y2="{H - 34}" stroke="{RULE}"/>'
                 f'<text x="{X(y)}" y="{H - 16}" class="tick" text-anchor="middle">{y}</text>')
    body = []
    for i, r in enumerate(md):
        cy = top + i * row_h + row_h / 2
        era = int(r["era"])
        lo, hi, med = int(r["present_min"]), int(r["present_max"]), int(r["assumed_present"])
        s.append(f'<text x="{left - 14}" y="{cy + 4}" class="lab" text-anchor="end">{esc(short(r["model"]))}</text>')
        s.append(f'<circle cx="{X(era)}" cy="{cy}" r="7" fill="none" stroke="{MUTE}" stroke-width="1.5">'
                 f'<title>release group {era}</title></circle>')
        if hi > lo:
            s.append(f'<line x1="{X(lo)}" y1="{cy}" x2="{X(hi)}" y2="{cy}" stroke="{ERA_COLOR[era]}" stroke-width="2"/>')
        s.append(f'<circle cx="{X(med)}" cy="{cy}" r="4.5" fill="{ERA_COLOR[era]}" stroke="{PAPER}" stroke-width="2">'
                 f'<title>{esc(short(r["model"]))}: believes it is {med} (range {lo} to {hi})</title></circle>')
        body.append([short(r["model"]), era, med, f"{lo} to {hi}"])
    s.append("</svg>")
    return {"title": "The moving present",
            "caption": (            "<p>The year each model says it is now (median of its runs, 18 to 20 per model, line = range). "
            "13 of the 24 models place the present one or two years before their release group (the ring); "
            "9 match it; 2 (gpt-3.5-turbo-0613 and gpt-5) place it one year later.</p>"),
            "svg": "".join(s), "table": table(["model", "release group", "believes it is", "range"], body)}


# ---------------------------------------------------------------- plate 3


def plate_pessimism() -> dict:
    md = rows("anchors_model.csv")
    tl = {r["model"]: r for r in rows("timeline_model.csv")}
    W, H = PW, 440
    # Panel A: scatter
    ax0, ax1, ay0, ay1 = 70, 410, 380, 50
    xs = [float(r["index_non_catastrophe"]) for r in md]
    ys = [float(r["index_catastrophe"]) for r in md]
    xlo, xhi, ylo, yhi = 0.45, 0.78, 0.10, 0.56

    def SX(v):
        return ax0 + (v - xlo) / (xhi - xlo) * (ax1 - ax0)

    def SY(v):
        return ay0 - (v - ylo) / (yhi - ylo) * (ay0 - ay1)
    s = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-labelledby="p3t">',
         '<title id="p3t">Catastrophe probability against the general level of probability, and negative events by era</title>']
    for v in (0.5, 0.6, 0.7):
        s.append(f'<line x1="{SX(v)}" y1="{ay1}" x2="{SX(v)}" y2="{ay0}" stroke="{RULE}"/>'
                 f'<text x="{SX(v)}" y="{ay0 + 18}" class="tick" text-anchor="middle">{v:.1f}</text>')
    for v in (0.2, 0.3, 0.4, 0.5):
        s.append(f'<line x1="{ax0}" y1="{SY(v)}" x2="{ax1}" y2="{SY(v)}" stroke="{RULE}"/>'
                 f'<text x="{ax0 - 8}" y="{SY(v) + 4}" class="tick" text-anchor="end">{v:.1f}</text>')
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    slope = sum((a - mx) * (b - my) for a, b in zip(xs, ys)) / sum((a - mx) ** 2 for a in xs)
    icpt = my - slope * mx
    s.append(f'<line x1="{SX(xlo)}" y1="{SY(icpt + slope * xlo)}" x2="{SX(xhi)}" y2="{SY(icpt + slope * xhi)}" '
             f'stroke="{MUTE}" stroke-width="1.5" stroke-dasharray="5 4"/>')
    labelled = sorted(md, key=lambda r: -float(r["catastrophe_residual"]))
    label_set = {r["model"] for r in labelled[:4] + labelled[-2:]}
    placed = []
    for r in md:
        era = int(r["era"])
        x, y = SX(float(r["index_non_catastrophe"])), SY(float(r["index_catastrophe"]))
        tip = (f'{short(r["model"])} ({era}): catastrophe {r["index_catastrophe"]}, '
               f'other events {r["index_non_catastrophe"]}, residual {r["catastrophe_residual"]}')
        s.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="{ERA_COLOR[era]}" stroke="{PAPER}" stroke-width="2">'
                 f'<title>{esc(tip)}</title></circle>')
        if r["model"] in label_set:
            ly, name = y + 4, short(r["model"])
            w = 7 * len(name)

            def hits(x0, x1, yy):
                return any(abs(yy - py) < 12 and x0 < qx1 and qx0 < x1 for qx0, qx1, py in placed)
            if not hits(x + 8, x + 8 + w, ly):
                box, tx, anchor = (x + 8, x + 8 + w), x + 8, "start"
            elif not hits(x - 8 - w, x - 8, ly):
                box, tx, anchor = (x - 8 - w, x - 8), x - 8, "end"
            else:
                ly -= 14
                box, tx, anchor = (x - w / 2, x + w / 2), x, "middle"
            placed.append((box[0], box[1], ly))
            s.append(f'<text x="{tx:.1f}" y="{ly:.1f}" class="small" text-anchor="{anchor}">{esc(name)}</text>')
    s.append(f'<text x="{(ax0 + ax1) / 2}" y="{H - 8}" class="lab" text-anchor="middle">mean probability of the other 22 events</text>'
             f'<text x="16" y="{(ay0 + ay1) / 2}" class="lab" text-anchor="middle" '
             f'transform="rotate(-90 16 {(ay0 + ay1) / 2})">mean probability of 6 catastrophes</text>')
    # Panel B: negative share of timeline events, by era
    bx0, bx1 = 505, PW - 16
    bylo, byhi = 0.0, 0.40

    def BY(v):
        return ay0 - (v - bylo) / (byhi - bylo) * (ay0 - ay1)
    eras = sorted(ERA_COLOR)
    step = (bx1 - bx0) / len(eras)
    for v in (0.0, 0.1, 0.2, 0.3, 0.4):
        s.append(f'<line x1="{bx0}" y1="{BY(v)}" x2="{bx1}" y2="{BY(v)}" stroke="{RULE}"/>'
                 f'<text x="{bx0 - 8}" y="{BY(v) + 4}" class="tick" text-anchor="end">{int(v * 100)}%</text>')
    by_era = defaultdict(list)
    for r in md:
        by_era[int(r["era"])].append(r["model"])
    for i, era in enumerate(eras):
        cx = bx0 + step * (i + 0.5)
        s.append(f'<text x="{cx}" y="{ay0 + 18}" class="tick" text-anchor="middle">{era}</text>')
        vals = sorted((float(tl[m]["share_negative"]), m) for m in by_era[era] if m in tl)
        for j, (v, m) in enumerate(vals):
            off = (j - (len(vals) - 1) / 2) * 7
            s.append(f'<circle cx="{cx + off:.1f}" cy="{BY(v):.1f}" r="4.5" fill="{ERA_COLOR[era]}" stroke="{PAPER}" '
                     f'stroke-width="2"><title>{esc(short(m))}: {v:.0%} of timeline events negative</title></circle>')
        med = sorted(v for v, _ in vals)[len(vals) // 2] if len(vals) % 2 else sum(sorted(v for v, _ in vals)[len(vals) // 2 - 1:len(vals) // 2 + 1]) / 2
        s.append(f'<line x1="{cx - 22}" y1="{BY(med)}" x2="{cx + 22}" y2="{BY(med)}" stroke="{INK}" stroke-width="2">'
                 f'<title>{era} median: {med:.0%}</title></line>')
    s.append(f'<text x="{bx1}" y="{H - 8}" class="lab" text-anchor="end">share of timeline events that are negative</text>')
    s.append(legend_era(ax0, 20))
    s.append("</svg>")
    body = [[short(r["model"]), r["era"], r["index_catastrophe"], r["index_non_catastrophe"],
             r["catastrophe_residual"], tl.get(r["model"], {}).get("share_negative", "")] for r in md]
    return {"title": "Do newer machines fear more?",
            "caption": (            "<p>Left: each model's mean probability of six catastrophes against its mean probability of the other events. "
            "Models that give high probabilities to everything sit to the right; the dashed line is that general habit. "
            "Models above the line fear more than their habit predicts. "
            "Right: the share of negative events in the free timelines, which has no probability scale.</p>"),
            "svg": "".join(s), "table": table(["model", "era", "catastrophe index", "other events", "residual", "timeline negative share"], body)}


# ---------------------------------------------------------------- plate 4


RAMP = ["#141a22", "#16304f", "#1d4677", "#245ea3", "#3987e5", "#6da7ec", "#a4c9f4", "#d6e7fb"]  # dark to light


def ramp(t: float) -> str:
    t = max(0.0, min(1.0, t)) * (len(RAMP) - 1)
    i = min(int(t), len(RAMP) - 2)
    return mix(RAMP[i], RAMP[i + 1], t - i)


def mix(c1: str, c2: str, t: float) -> str:
    a = [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(c2[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(a, b))


def plate_themes() -> dict:
    hz = rows("timeline_horizon.csv")
    themes = [k[6:] for k in hz[0] if k.startswith("theme_")]
    peak = {t: max(range(len(hz)), key=lambda i: float(hz[i][f"theme_{t}"])) for t in themes}
    themes = [t for t in themes if max(float(h[f"theme_{t}"]) for h in hz) >= 0.03]
    themes.sort(key=lambda t: (peak[t], -max(float(h[f"theme_{t}"]) for h in hz)))
    W, left, top = PW, 206, 40
    cw = (W - left - 20) / len(hz)
    ch = 26
    H = top + ch * len(themes) + 84
    vmax = max(float(h[f"theme_{t}"]) for h in hz for t in themes)
    s = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-labelledby="p4t">',
         '<title id="p4t">Share of timeline events by theme and horizon</title>']
    for j, h in enumerate(hz):
        s.append(f'<text x="{left + cw * (j + 0.5):.1f}" y="{top - 10}" class="small" text-anchor="middle">{esc(h["horizon"])}</text>')
    body = []
    for i, t in enumerate(themes):
        y = top + i * ch
        s.append(f'<text x="{left - 12}" y="{y + ch / 2 + 4}" class="lab" text-anchor="end">{esc(t.replace("_", " "))}</text>')
        for j, h in enumerate(hz):
            v = float(h[f"theme_{t}"])
            col = ramp(min(v / vmax, 1) ** 0.8)
            s.append(f'<rect x="{left + cw * j + 1:.1f}" y="{y + 1}" width="{cw - 2:.1f}" height="{ch - 2}" rx="2" fill="{col}">'
                     f'<title>{esc(t)}, {esc(h["horizon"])}: {v:.0%} of events</title></rect>')
            if v >= 0.10:
                fill = PAPER if (v / vmax) ** 0.8 > 0.6 else INK
                s.append(f'<text x="{left + cw * (j + 0.5):.1f}" y="{y + ch / 2 + 4}" class="small" '
                         f'text-anchor="middle" style="fill:{fill}">{v:.0%}</text>')
        body.append([t] + [f'{float(h[f"theme_{t}"]):.0%}' for h in hz])
    sim_y = top + ch * len(themes) + 22
    s.append(f'<text x="{left - 12}" y="{sim_y}" class="lab" text-anchor="end">similarity between models</text>')
    for j, h in enumerate(hz):
        s.append(f'<text x="{left + cw * (j + 0.5):.1f}" y="{sim_y}" class="small" text-anchor="middle">'
                 f'{float(h["similarity_between_models"]):.2f}</text>')
    key_y = sim_y + 22  # colour scale
    s.append(f'<text x="{left - 12}" y="{key_y + 11}" class="lab" text-anchor="end">share of events</text>'
             f'<text x="{left + 2}" y="{key_y + 11}" class="small">0%</text>')
    for k in range(9):
        s.append(f'<rect x="{left + 30 + k * 22}" y="{key_y}" width="21" height="14" rx="2" fill="{ramp((k / 8) ** 0.8)}"/>')
    s.append(f'<text x="{left + 30 + 9 * 22 + 6}" y="{key_y + 11}" class="small">{vmax:.0%}</text>')
    s.append("</svg>")
    return {"title": "What the future is made of",
            "caption": (            "<p>Share of timeline events in each theme, by horizon (each model weighted equally). "
            "To 2030: AI, climate and energy. From 2031 to 2500: the solar system and climate among the largest themes. "
            "From 2501: the stars, and after 3000 also posthumans and megastructures. "
            "Bottom row: how alike the models' theme mix is in each horizon (1 = the same).</p>"),
            "svg": "".join(s), "table": table(["theme"] + [h["horizon"] for h in hz], body)}


# ---------------------------------------------------------------- plate 5


# Short names for the labels of plate 5. The tooltip and the table keep the full name.
SHORT_EVENT = {
    "Dyson swarm construction and capture of solar output": "Dyson swarm",
    "First human settlement in another star system": "Settlement in another star system",
    "Humanity diverges into distinct lineages": "Humanity diverges into lineages",
    "Ecosystems and biodiversity restored": "Ecosystems restored",
    "Multi-meter sea-level rise from ice sheets": "Multi-meter sea-level rise",
    "Civilizational collapse or dark age": "Collapse or dark age",
    "Post-scarcity economy emerges": "Post-scarcity economy",
    "Mass climate migration and refugee crisis": "Mass climate migration",
    "Severe pandemic or engineered pathogen": "Severe or engineered pandemic",
    "Major AI-enabled attack or rogue-AI crisis": "AI attack or rogue-AI crisis",
    "Aging therapies extend healthy lifespan": "Aging therapies",
    "Natural cosmic hazard to civilization": "Natural cosmic hazard",
    "Sea-level rise forces coastal retreat": "Coastal retreat from the sea",
}


def plate_standard_future() -> dict:
    ce = [r for r in rows("canonical_events.csv") if r["median_year"]]
    W, H = PW, 600
    x0, x1, y0, y1 = 64, PW - 24, 530, 34
    BLUE, ORANGE = POS, NEG

    def Y(n):
        return y0 - n / 24 * (y0 - y1)
    s = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-labelledby="p5t">',
         '<title id="p5t">Canonical events by median year and number of models that use them</title>']
    for yr in (2030, 2050, 2100, 2200, 2500, 3000, 5000, 10000):
        x = log_x(yr, x0, x1)
        s.append(f'<line x1="{x:.1f}" y1="{y1}" x2="{x:.1f}" y2="{y0}" stroke="{RULE}"/>'
                 f'<text x="{x:.1f}" y="{y0 + 18}" class="tick" text-anchor="middle">{yr}</text>')
    for n in (0, 6, 12, 18, 24):
        s.append(f'<line x1="{x0}" y1="{Y(n)}" x2="{x1}" y2="{Y(n)}" stroke="{RULE}"/>'
                 f'<text x="{x0 - 8}" y="{Y(n) + 4}" class="tick" text-anchor="end">{n}</text>')
    s.append(f'<text x="16" y="{(y0 + y1) / 2}" class="lab" text-anchor="middle" '
             f'transform="rotate(-90 16 {(y0 + y1) / 2})">models that write it (of 24)</text>')
    s.append(f'<circle cx="{x0 + 10}" cy="{H - 16}" r="5" fill="{BLUE}"/><text x="{x0 + 20}" y="{H - 11}" class="lab">mostly positive or neutral</text>'
             f'<circle cx="{x0 + 230}" cy="{H - 16}" r="5" fill="{ORANGE}"/><text x="{x0 + 240}" y="{H - 11}" class="lab">mostly negative</text>')
    placed, body = [], []
    for r in ce:  # dots are obstacles for labels
        placed.append((log_x(int(r["median_year"]), x0, x1) - 8, Y(int(r["models"])) + 4, 16))
    for r in sorted(ce, key=lambda r: -int(r["models"])):
        n, yr = int(r["models"]), int(r["median_year"])
        neg = float(r["share_negative"] or 0) >= 0.5
        x, y = log_x(yr, x0, x1), Y(n)
        col = ORANGE if neg else BLUE
        s.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="{col}" stroke="{PAPER}" stroke-width="2">'
                 f'<title>{esc(r["label"])}: {yr}, {n} models, {float(r["share_negative"] or 0):.0%} negative</title></circle>')
        body.append([r["label"], yr, f'{r["q1_year"]} to {r["q3_year"]}', n, f'{float(r["share_negative"] or 0):.0%}'])
    wanted = [r for r in ce if int(r["models"]) >= 20 or (float(r["share_negative"] or 0) >= 0.5 and int(r["models"]) >= 10)]
    for r in sorted(wanted, key=lambda r: -int(r["median_year"])):
        x, y = log_x(int(r["median_year"]), x0, x1), Y(int(r["models"]))
        name = SHORT_EVENT.get(r["label"], r["label"])
        w = 7.0 * len(name) + 4
        # Nearest free place first; a place away from the dot gets a leader line.
        cands = [(8, 4, "start"), (-8, 4, "end")]
        for dy in (-10, 19, -24, 33, -38, 47, -52, 61, -66, 75):
            cands += [(0, dy, "middle"), (10, dy, "start"), (-10, dy, "end")]
        for dx, dy, anchor in cands:
            bx = x + dx if anchor == "start" else (x + dx - w if anchor == "end" else x - w / 2)
            by = y + dy
            if bx >= 4 and bx + w <= W - 4 and 14 < by < y0 - 4 and not any(
                    abs(by - py) < 14 and bx < qx + qw and qx < bx + w for qx, py, qw in placed):
                placed.append((bx, by, w))
                if abs(dy) > 20:
                    ly = by + 3 if dy < 0 else by - 12
                    s.append(f'<line x1="{x:.1f}" y1="{y + (-6 if dy < 0 else 6):.1f}" x2="{x + dx * 0.6:.1f}" y2="{ly:.1f}" '
                             f'stroke="{MUTE}" stroke-width="0.75"/>')
                s.append(f'<text x="{x + dx:.1f}" y="{by:.1f}" class="small" text-anchor="{anchor}">{esc(name)}</text>')
                break
        else:
            print(f"plate 5: no room for the label of {name}")
    s.append("</svg>")
    return {"title": "The standard future",
            "caption": (            "<p>The events that the timelines repeat, found without the anchors: one dot per canonical event, "
            "at the median year of the models that write it, and as high as the number of models that write it. "
            "14 events reach 20 or more of the 24 models, and none of them is mostly negative. "
            "The most common negative event, mass climate migration, is in 18. "
            "Of the 11 negative events in 10 or more models, 8 fall in this century: five climate events, "
            "a pandemic, a nuclear or bioweapon catastrophe and an AI attack.</p>"),
            "svg": "".join(s), "table": table(["event", "median year", "IQR of model medians", "models", "negative"], body)}



def all_plates() -> dict:
    """Plates in essay order, keyed by the id used in the site markers."""
    return {"present": plate_present(), "anchor-years": plate_anchor_years(),
            "themes": plate_themes(), "pessimism": plate_pessimism(),
            "standard-future": plate_standard_future()}


def main() -> None:
    cfg = tomllib.loads((ROOT / "config.toml").read_text())
    n_models = len(cfg["models"])
    OUT.mkdir(exist_ok=True)
    plates = all_plates()
    drafts_body = "\n".join(f'<h2>{p["title"]}</h2><p>{p["caption"]}</p>{p["svg"]}{p["table"]}' for p in plates.values())
    page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Pythia plates</title>
<style>
body {{ background: {PAPER}; color: {INK}; font-family: {FONT}; margin: 0 auto; max-width: 1000px; padding: 24px 16px 80px; }}
h1 {{ font-weight: 400; font-size: 2.4rem; margin-bottom: 0.2rem; }}
h2 {{ font-weight: 600; font-size: 1.4rem; margin-top: 3rem; }}
p {{ color: {INK_SOFT}; max-width: 70ch; line-height: 1.5; }}
svg {{ width: 100%; height: auto; display: block; margin: 1rem 0; }}
svg .lab {{ font: 15px {FONT}; fill: {INK_SOFT}; }}
svg .tick {{ font: 14px {FONT}; fill: {MUTE}; }}
svg .small {{ font: 13px {FONT}; fill: {INK_SOFT}; }}
details {{ margin: 0.5rem 0 1rem; color: {INK_SOFT}; }}
table {{ border-collapse: collapse; font-size: 0.85rem; margin-top: 0.5rem; }}
td, th {{ border-bottom: 1px solid {RULE}; padding: 3px 10px 3px 0; text-align: left; }}
</style></head><body>
<h1>Pythia: draft plates</h1>
<p>Do machines agree on our future? {n_models} language models, 2023 to 2026, 10 runs each, blind to each other.
Drafts generated by scripts/plates.py from data/analysis. Hover a mark for its value.</p>
{drafts_body}
</body></html>
"""
    (OUT / "drafts.html").write_text(page)
    print(f"wrote {OUT / 'drafts.html'}")


if __name__ == "__main__":
    main()
