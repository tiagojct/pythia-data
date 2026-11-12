"""Code the timeline events with an LLM coder and a fixed codebook (coding/codebook.md).

Usage:
    uv run scripts/code_timeline.py                      # main coder, all events
    uv run scripts/code_timeline.py --check              # second coder on a sample, agreement
    uv run scripts/code_timeline.py --handcheck          # sample for checking by hand

The coder does not see the model names. Batches mix events from all models in a
fixed random order. Each batch response is saved in data/coded/raw/<coder>/;
a batch file that exists is skipped, so a stopped run continues.

Output:
    data/coded/codes_<coder>.csv   model, run, order, theme, valence, anchor
    data/coded/agreement.md        (with --check) Cohen's kappa between the coders
    data/coded/handcheck.csv       (with --handcheck) 120 events to check by hand
"""

import argparse
import csv
import json
import os
import random
import re
import sys
import tomllib
import urllib.error
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from parse import extract_json  # noqa: E402

API = "https://openrouter.ai/api/v1/chat/completions"
EVENTS = ROOT / "data" / "parsed" / "timeline_events.csv"
OUT = ROOT / "data" / "coded"

MAIN_CODER = "anthropic/claude-haiku-5.5"   # not in the model set
CHECK_CODER = "openai/gpt-6-luna"           # not in the model set
BATCH = 60
CHECK_SAMPLE = 600
HANDCHECK_SAMPLE = 120
SEED = 20261112

THEMES = re.findall(r"^- ([a-z_]+):", (ROOT / "coding" / "codebook.md").read_text().split("## Valence")[0], re.M)
VALENCES = ("positive", "negative", "neutral")


def slug(model_id: str) -> str:
    return model_id.replace("/", "__").replace(":", "_")


def load_events() -> list[dict]:
    rows = list(csv.DictReader(EVENTS.open()))
    rows.sort(key=lambda r: (r["model"], int(r["run"]), int(r["order"])))
    random.Random(SEED).shuffle(rows)
    return rows


def codebook_text() -> str:
    cfg = tomllib.loads((ROOT / "config.toml").read_text())
    anchors = "\n".join(f"- {a['id']}: {a['text']}" for a in cfg["anchors"])
    return (ROOT / "coding" / "codebook.md").read_text().replace("{anchors}", anchors)


def prompt(book: str, batch: list[dict]) -> str:
    lines = "\n".join(
        f'{i}. [{r["year"]}] {r["event"]}' + (f' ({r["detail"]})' if r["detail"] else "")
        for i, r in enumerate(batch, 1)
    )
    return (
        "You code events from forecasts of the future of humanity. Use the codebook.\n\n"
        f"{book}\n\n## Events\n\n{lines}\n\n"
        "Reply with JSON only, in this form, with one item for each event number:\n"
        '{"codes": [{"n": 1, "theme": "<theme>", "valence": "<positive|negative|neutral>", '
        '"anchor": "<anchor id or null>"}]}'
    )


def call(key: str, model: str, text: str) -> dict:
    body = {"model": model, "messages": [{"role": "user", "content": text}],
            "temperature": 0, "usage": {"include": True}}
    req = urllib.request.Request(API, data=json.dumps(body).encode(), headers={
        "Authorization": f"Bearer {key}", "Content-Type": "application/json", "X-Title": "pythia"})
    with urllib.request.urlopen(req, timeout=600) as resp:
        return json.load(resp)


def run_batches(key: str, coder: str, events: list[dict], workers: int = 6) -> None:
    book = codebook_text()
    folder = OUT / "raw" / slug(coder)
    folder.mkdir(parents=True, exist_ok=True)
    batches = [events[i:i + BATCH] for i in range(0, len(events), BATCH)]

    def job(k: int, batch: list[dict]) -> str:
        path = folder / f"batch-{k:03d}.json"
        if path.exists():
            return ""
        try:
            data = call(key, coder, prompt(book, batch))
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            return f"FAIL batch {k}: {e}"
        keys = [[r["model"], r["run"], r["order"]] for r in batch]
        path.write_text(json.dumps({"coder": coder, "keys": keys, "response": data}, ensure_ascii=False))
        return ""

    with ThreadPoolExecutor(workers) as pool:
        fails = [f.result() for f in as_completed(pool.submit(job, k, b) for k, b in enumerate(batches))]
    fails = [f for f in fails if f]
    for f in fails:
        print(f)
    print(f"{coder}: {len(batches)} batches, {len(fails)} failed")


def collect(coder: str) -> list[dict]:
    """Read the saved batches and return one row per event, with problems flagged."""
    rows, cost = [], 0.0
    anchor_ids = {a["id"] for a in tomllib.loads((ROOT / "config.toml").read_text())["anchors"]}
    for path in sorted((OUT / "raw" / slug(coder)).glob("batch-*.json")):
        rec = json.loads(path.read_text())
        resp = rec["response"]
        cost += (resp.get("usage") or {}).get("cost") or 0
        text = (resp.get("choices") or [{}])[0].get("message", {}).get("content") or ""
        obj, _ = extract_json(text)
        codes = {int(c.get("n", 0)): c for c in (obj or {}).get("codes", []) if isinstance(c, dict)}
        for i, (model, run, order) in enumerate(rec["keys"], 1):
            c = codes.get(i, {})
            theme = c.get("theme") if c.get("theme") in THEMES else ""
            valence = c.get("valence") if c.get("valence") in VALENCES else ""
            anchor = c.get("anchor")
            anchor = anchor if anchor in anchor_ids else ""
            flag = "missing" if not c else ("bad_value" if not (theme and valence) else "")
            rows.append({"model": model, "run": run, "order": order, "theme": theme,
                         "valence": valence, "anchor": anchor, "flag": flag})
    print(f"{coder}: {len(rows)} coded events, cost {cost:.2f} USD, "
          f"problems {sum(1 for r in rows if r['flag'])}")
    return rows


def write(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def kappa(a: list[str], b: list[str]) -> float:
    n = len(a)
    po = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[k] * cb[k] for k in set(a) | set(b)) / n ** 2
    return (po - pe) / (1 - pe) if pe < 1 else 1.0


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--check", action="store_true", help="second coder on a sample")
    p.add_argument("--handcheck", action="store_true", help="write a sample to check by hand")
    args = p.parse_args()
    events = load_events()
    OUT.mkdir(parents=True, exist_ok=True)
    key = os.environ.get("OPENROUTER_API_KEY")

    if args.handcheck:
        codes = {(r["model"], r["run"], r["order"]): r for r in
                 csv.DictReader((OUT / f"codes_{slug(MAIN_CODER)}.csv").open())}
        sample = random.Random(SEED + 2).sample(events, HANDCHECK_SAMPLE)
        rows = []
        for e in sample:
            c = codes[(e["model"], e["run"], e["order"])]
            rows.append({"year": e["year"], "event": e["event"], "detail": e["detail"],
                         "theme": c["theme"], "valence": c["valence"], "anchor": c["anchor"],
                         "theme_ok": "", "valence_ok": "", "anchor_ok": "", "note": "",
                         "model": e["model"], "run": e["run"], "order": e["order"]})
        write(OUT / "handcheck.csv", rows)
        print(f"wrote {OUT / 'handcheck.csv'}: {len(rows)} events. Fill the *_ok columns with y or n.")
        return

    if not key:
        sys.exit("Set OPENROUTER_API_KEY in the environment.")

    if args.check:
        sample = random.Random(SEED + 1).sample(events, CHECK_SAMPLE)
        run_batches(key, CHECK_CODER, sample)
        main_codes = {(r["model"], r["run"], r["order"]): r for r in
                      csv.DictReader((OUT / f"codes_{slug(MAIN_CODER)}.csv").open())}
        check = collect(CHECK_CODER)
        write(OUT / f"codes_{slug(CHECK_CODER)}.csv", check)
        pairs = [(main_codes[(r["model"], r["run"], r["order"])], r) for r in check
                 if (r["model"], r["run"], r["order"]) in main_codes
                 and not r["flag"] and not main_codes[(r["model"], r["run"], r["order"])]["flag"]]
        lines = ["# Coder agreement", "",
                 f"Main coder {MAIN_CODER}, check coder {CHECK_CODER}, {len(pairs)} events.", ""]
        for field in ("theme", "valence", "anchor"):
            a = [m[field] or "none" for m, _ in pairs]
            b = [c[field] or "none" for _, c in pairs]
            agree = sum(x == y for x, y in zip(a, b)) / len(pairs)
            lines.append(f"- {field}: agreement {agree:.2f}, Cohen's kappa {kappa(a, b):.2f}")
        conf = Counter((m["theme"], c["theme"]) for m, c in pairs if m["theme"] != c["theme"])
        lines += ["", "Most frequent theme disagreements (main, check):", ""]
        lines += [f"- {a} / {b}: {n}" for (a, b), n in conf.most_common(12)]
        (OUT / "agreement.md").write_text("\n".join(lines) + "\n")
        print("\n".join(lines))
        return

    run_batches(key, MAIN_CODER, events)
    rows = collect(MAIN_CODER)
    write(OUT / f"codes_{slug(MAIN_CODER)}.csv", rows)


if __name__ == "__main__":
    main()
