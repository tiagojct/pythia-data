"""Numbers for the philosophical passages of the essay (added 2026-11-13).

Reads data/parsed/ and data/analysis/ and writes data/analysis/readings.md.

Some numbers come from keyword searches. Others come from a reading by hand of
the matched texts; those readings are written below as constants, and the
script prints the texts again so that a reader can check each label.

- The 13 timeline runs that answer "no" to "will humanity exist in 10000?":
  each summary read and labelled (descendants that are no longer human, or the
  end of the universe).
- The "yes" runs whose summary writes of posthuman or post-biological forms
  (keyword search, each match read).
- Events about the heat death of the universe before 10000: the models whose
  events say that it arrives or comes near (read by hand), against the models
  that only plan or experiment against it.
- The intraclass correlation of the probabilities (median over the 28 events)
  and the run-to-run range of gpt-4 for extinction.
- The median theme shares in the free timelines.
"""

import csv
import re
import statistics as st
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PARSED = ROOT / "data" / "parsed"
ANALYSIS = ROOT / "data" / "analysis"

# Reading by hand of the 13 "no" summaries (model, run) -> label.
NO_LABELS = {
    ("anthropic/claude-opus-4.1", "3"): "descendants",
    ("anthropic/claude-opus-4.1", "6"): "descendants",
    ("anthropic/claude-opus-4.1", "9"): "descendants",
    ("openai/gpt-4", "1"): "descendants",
    ("openai/gpt-4", "2"): "descendants",
    ("openai/gpt-4", "5"): "descendants",
    ("openai/gpt-4", "7"): "descendants",
    ("openai/gpt-4", "10"): "descendants",
    ("moonshotai/kimi-k2", "9"): "descendants",
    ("meta-llama/llama-3.1-70b-instruct", "6"): "descendants",
    ("meta-llama/llama-3.1-70b-instruct", "1"): "end of the universe",
    ("meta-llama/llama-3.1-70b-instruct", "3"): "end of the universe",
    ("meta-llama/llama-3.1-70b-instruct", "7"): "end of the universe",
}

# Reading by hand of the events that name the heat death of the universe before
# 10000: the models with at least one event in which it arrives or comes near.
HEAT_DEATH_ARRIVES = {
    "meta-llama/llama-3.1-70b-instruct",   # "The heat death of the universe begins" (2500)
    "meta-llama/llama-4-maverick",          # "The universe's heat death is imminent" (10000)
    "mistralai/mixtral-8x22b-instruct",     # "confronts insurmountable heat death acceleration" (8000)
    "mistralai/mistral-large-4-0",          # "to survive the approaching heat death" (9000)
}

POSTHUMAN = re.compile(r"post-?biolog|post-?human|transcend|\bmerg", re.I)


def main() -> None:
    runs = [r for r in csv.DictReader((PARSED / "runs.csv").open()) if r["prompt"] == "timeline"]
    L = ["# Readings: numbers for the philosophical passages", "",
         "Written by scripts/analyse_readings.py. Labels marked 'by hand' are constants in the script.", ""]

    # 1. "No" answers
    no = [r for r in runs if r["humanity_10000"].strip().lower() == "no"]
    missing = {(r["model"], r["run"]) for r in no} ^ set(NO_LABELS)
    if missing:
        raise SystemExit(f"the 'no' runs changed; read them again: {sorted(missing)}")
    counts = {}
    for lab in NO_LABELS.values():
        counts[lab] = counts.get(lab, 0) + 1
    L += [f"## Runs that answer no: {len(no)}", ""]
    L += [f"- {lab} (by hand): {n}" for lab, n in sorted(counts.items())]
    L += [""] + [f"- {r['model']} run {r['run']} [{NO_LABELS[(r['model'], r['run'])]}]: {r['summary']}"
                 for r in no] + [""]

    # 2. "Yes" answers with posthuman words
    yes = [r for r in runs if r["humanity_10000"].strip().lower() == "yes"]
    ph = [r for r in yes if POSTHUMAN.search(r["summary"])]
    L += [f"## Runs that answer yes: {len(yes)}; summary writes of posthuman or post-biological forms: {len(ph)}",
          "", f"Pattern: {POSTHUMAN.pattern} (each match read by hand).", ""]
    L += [f"- {r['model']} run {r['run']}: {r['summary']}" for r in ph] + [""]

    # 3. Heat death
    ev = list(csv.DictReader((PARSED / "timeline_events.csv").open()))
    hd = [e for e in ev if re.search("heat death", e["event"] + " " + e["detail"], re.I)
          and e["year"].lstrip("-").isdigit() and int(e["year"]) <= 10000]
    models = sorted({e["model"] for e in hd})
    L += [f"## Events that name the heat death of the universe, year 10000 or earlier: {len(hd)}, "
          f"from {len(models)} models", "",
          f"Models with an event in which it arrives or comes near (by hand): {len(HEAT_DEATH_ARRIVES)}", ""]
    L += [f"- {e['model']} {e['year']}: {e['event']}" for e in hd] + [""]

    # 4. Probabilities
    ae = list(csv.DictReader((ANALYSIS / "anchors_event.csv").open()))
    icc = [float(r["icc_prob"]) for r in ae if r["icc_prob"]]
    gpt4 = [(a["run"], a["probability"], a["flag"]) for a in csv.DictReader((PARSED / "anchors.csv").open())
            if a["model"] == "openai/gpt-4" and a["id"] == "extinction"]
    L += ["## Probabilities", "",
          f"Intraclass correlation of the probability, median over {len(icc)} events: {st.median(icc):.2f} "
          f"(range {min(icc):.2f} to {max(icc):.2f})", "",
          "gpt-4, extinction, by run (run, probability, flag): " + "; ".join(", ".join(x) for x in gpt4), ""]

    # 5. Theme shares
    tm = list(csv.DictReader((ANALYSIS / "timeline_model.csv").open()))
    def med(f):
        return st.median(f(r) for r in tm)
    L += ["## Median theme shares over models (free timelines)", "",
          f"- space (solar system and interstellar): {med(lambda r: float(r['theme_space_solar_system']) + float(r['theme_space_interstellar'])):.3f}",
          f"- culture_society: {med(lambda r: float(r['theme_culture_society'])):.3f}",
          f"- war_conflict: {med(lambda r: float(r['theme_war_conflict'])):.3f}",
          f"- governance: {med(lambda r: float(r['theme_governance'])):.3f}",
          f"- share of events after 3000: {med(lambda r: float(r['share_after_3000'])):.3f}", ""]

    out = ANALYSIS / "readings.md"
    out.write_text("\n".join(L))
    print(f"wrote {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
