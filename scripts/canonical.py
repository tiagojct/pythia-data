"""Find the canonical events (the events that many timelines repeat) and assign each event to one.

Usage:
    uv run scripts/canonical.py propose   # proposer model writes coding/canonical.json from a sample
    uv run scripts/canonical.py assign    # coder assigns every event to a canonical id or "other"

Proposer: claude-sonnet-5.5. Coder: claude-haiku-5.5. Neither is in the model set,
and neither sees the model names. Read and edit coding/canonical.json before assign:
the list is the codebook for this step.

Output: data/coded/canonical_codes.csv (model, run, order, canonical).
"""

import csv
import json
import os
import random
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from code_timeline import call, load_events, slug  # noqa: E402
from parse import extract_json  # noqa: E402

PROPOSER = "anthropic/claude-sonnet-5.5"
CODER = "anthropic/claude-haiku-5.5"
LIST = ROOT / "coding" / "canonical.json"
OUT = ROOT / "data" / "coded"
SAMPLE = 1200
BATCH = 60
SEED = 20261113


def horizon_bin(y: int) -> int:
    for i, top in enumerate((2030, 2050, 2100, 2200, 2500, 3000, 5000, 10_000)):
        if y <= top:
            return i
    return 7


def propose(key: str) -> None:
    events = [e for e in load_events() if e["year"]]
    # Stratify by model and horizon, so no model and no period dominates the sample.
    cells = defaultdict(list)
    for e in events:
        cells[(e["model"], horizon_bin(int(e["year"])))].append(e)
    rng = random.Random(SEED)
    per_cell = max(1, SAMPLE // len(cells))
    sample = [e for c in cells.values() for e in rng.sample(c, min(per_cell, len(c)))]
    rng.shuffle(sample)
    lines = "\n".join(f'- [{e["year"]}] {e["event"]}' for e in sample)
    text = (
        "Below is a sample of events from many forecasts of the future of humanity to the year 10000.\n\n"
        "Make a list of the canonical events: the events that come back again and again in different "
        "forecasts, in different words. Give between 60 and 90 canonical events. Each must be one specific "
        "event or state, not a broad theme (\"First crewed landing on Mars\", not \"Space\"). Merge events "
        "that say the same thing at a different date. Cover the whole period to 10000, and include the "
        "negative events that recur, not only the positive ones.\n\n"
        f"Events:\n{lines}\n\n"
        "Reply with JSON only:\n"
        '{"canonical": [{"id": "<short_snake_case>", "label": "<short label>", '
        '"definition": "<one sentence: what counts and what does not>"}]}'
    )
    data = call(key, PROPOSER, text)
    obj, flags = extract_json(data["choices"][0]["message"]["content"])
    if not obj or "canonical" not in obj:
        sys.exit(f"No list in the response ({flags}).")
    LIST.write_text(json.dumps({"proposer": PROPOSER, "sample": len(sample),
                                "canonical": obj["canonical"]}, indent=2, ensure_ascii=False))
    print(f"wrote {LIST}: {len(obj['canonical'])} canonical events, "
          f"cost {(data.get('usage') or {}).get('cost')}")


def assign(key: str) -> None:
    canon = json.loads(LIST.read_text())["canonical"]
    ids = {c["id"] for c in canon}
    book = "\n".join(f'- {c["id"]}: {c["label"]}. {c["definition"]}' for c in canon)
    events = load_events()
    folder = OUT / "raw" / f"canonical_{slug(CODER)}"
    folder.mkdir(parents=True, exist_ok=True)
    batches = [events[i:i + BATCH] for i in range(0, len(events), BATCH)]

    def prompt(batch):
        lines = "\n".join(f'{i}. [{e["year"]}] {e["event"]}' + (f' ({e["detail"]})' if e["detail"] else "")
                          for i, e in enumerate(batch, 1))
        return ("Assign each event to one canonical event from the list, or to \"other\" if none fits. "
                "The event must be the same event as the definition, at any date. A related event on the "
                "same topic is \"other\".\n\n"
                f"Canonical events:\n{book}\n\nEvents:\n{lines}\n\n"
                'Reply with JSON only: {"codes": [{"n": 1, "id": "<canonical id or other>"}]}')

    def job(k, batch):
        path = folder / f"batch-{k:03d}.json"
        if path.exists():
            return ""
        try:
            data = call(key, CODER, prompt(batch))
        except OSError as e:
            return f"FAIL batch {k}: {e}"
        path.write_text(json.dumps({"keys": [[e["model"], e["run"], e["order"]] for e in batch],
                                    "response": data}, ensure_ascii=False))
        return ""

    with ThreadPoolExecutor(6) as pool:
        fails = [f.result() for f in as_completed(pool.submit(job, k, b) for k, b in enumerate(batches))]
    for f in filter(None, fails):
        print(f)

    rows, cost, bad = [], 0.0, 0
    for path in sorted(folder.glob("batch-*.json")):
        rec = json.loads(path.read_text())
        cost += (rec["response"].get("usage") or {}).get("cost") or 0
        obj, _ = extract_json(rec["response"]["choices"][0]["message"].get("content") or "")
        codes = {int(c.get("n", 0)): c.get("id") for c in (obj or {}).get("codes", []) if isinstance(c, dict)}
        for i, (model, run, order) in enumerate(rec["keys"], 1):
            cid = codes.get(i)
            if cid not in ids and cid != "other":
                bad += 1
                cid = ""
            rows.append({"model": model, "run": run, "order": order, "canonical": cid})
    with (OUT / "canonical_codes.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} events assigned, {bad} without a valid code, cost {cost:.2f} USD")


def main() -> None:
    key = os.environ.get("OPENROUTER_API_KEY") or sys.exit("Set OPENROUTER_API_KEY in the environment.")
    step = sys.argv[1] if len(sys.argv) > 1 else ""
    if step == "propose":
        propose(key)
    elif step == "assign":
        assign(key)
    else:
        sys.exit("Usage: canonical.py propose | assign")


if __name__ == "__main__":
    main()
