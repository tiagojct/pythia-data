"""Send the pythia prompts to each model on OpenRouter and save the raw responses.

Usage:
    uv run scripts/run.py --dry-run
    uv run scripts/run.py --prompt all --runs 10
    uv run scripts/run.py --prompt anchors --runs 2 --models openai/gpt-4

One file per call: data/raw/<prompt>/<model-slug>/run-NN.json.
A file that exists is skipped. A failed call writes no file, so the next run tries again.
"""

import argparse
import json
import os
import random
import sys
import time
import tomllib
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
API = "https://openrouter.ai/api/v1/chat/completions"
PROMPTS = ("timeline", "anchors")


def slug(model_id: str) -> str:
    return model_id.replace("/", "__").replace(":", "_")


def build_prompt(name: str, anchors: list[dict], run: int) -> tuple[str, list[str] | None]:
    text = (ROOT / "prompts" / f"{name}.md").read_text()
    if name != "anchors":
        return text, None
    order = [a["id"] for a in anchors]
    random.Random(run).shuffle(order)
    by_id = {a["id"]: a["text"] for a in anchors}
    lines = "\n".join(f"- {i}: {by_id[i]}" for i in order)
    return text.replace("{events}", lines), order


def call(key: str, body: dict, timeout: int) -> tuple[dict, float]:
    req = urllib.request.Request(
        API,
        data=json.dumps(body).encode(),
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "X-Title": "pythia",
        },
    )
    start = time.monotonic()
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.load(resp)
    return data, time.monotonic() - start


def job(key: str, cfg: dict, model: dict, prompt: str, run: int) -> str:
    out = ROOT / "data" / "raw" / prompt / slug(model["id"]) / f"run-{run:02d}.json"
    if out.exists():
        return f"skip  {model['id']} {prompt} {run}"

    text, order = build_prompt(prompt, cfg["anchors"], run)
    body = {
        "model": model["id"],
        "messages": [{"role": "user", "content": text}],
        "temperature": cfg["run"]["temperature"],
        "usage": {"include": True},
    }
    if "max_tokens" in model:
        body["max_tokens"] = model["max_tokens"]
    if "reasoning" in model:
        body["reasoning"] = {"effort": model["reasoning"]}

    requested = datetime.now(timezone.utc).isoformat(timespec="seconds")
    try:
        data, seconds = call(key, body, cfg["run"]["timeout_s"])
    except urllib.error.HTTPError as e:
        return f"FAIL  {model['id']} {prompt} {run}: HTTP {e.code} {e.read()[:300]!r}"
    except Exception as e:  # network errors, timeouts
        return f"FAIL  {model['id']} {prompt} {run}: {e}"

    if "error" in data or not data.get("choices"):
        return f"FAIL  {model['id']} {prompt} {run}: {json.dumps(data)[:300]}"

    record = {
        "model": model["id"],
        "era": model["era"],
        "prompt": prompt,
        "run": run,
        "anchor_order": order,
        "requested_at": requested,
        "seconds": round(seconds, 1),
        "request": body,
        "response": data,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(record, indent=2, ensure_ascii=False))
    cost = (data.get("usage") or {}).get("cost")
    return f"ok    {model['id']} {prompt} {run} ({seconds:.0f} s, cost {cost})"


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--prompt", choices=(*PROMPTS, "all"), default="all")
    p.add_argument("--runs", type=int, default=10)
    p.add_argument("--models", help="comma-separated model ids; default: all enabled")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    cfg = tomllib.loads((ROOT / "config.toml").read_text())
    models = [m for m in cfg["models"] if m.get("enabled", True)]
    if args.models:
        wanted = set(args.models.split(","))
        models = [m for m in cfg["models"] if m["id"] in wanted]
        missing = wanted - {m["id"] for m in models}
        if missing:
            sys.exit(f"Not in config.toml: {', '.join(sorted(missing))}")
    prompts = PROMPTS if args.prompt == "all" else (args.prompt,)
    jobs = [(m, pr, r) for m in models for pr in prompts for r in range(1, args.runs + 1)]

    if args.dry_run:
        for m, pr, r in jobs:
            out = ROOT / "data" / "raw" / pr / slug(m["id"]) / f"run-{r:02d}.json"
            print(("exists " if out.exists() else "todo   ") + f"{m['id']} {pr} {r}")
        print(f"{len(jobs)} calls, {len(models)} models")
        return

    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        sys.exit("Set OPENROUTER_API_KEY in the environment.")

    failed = 0
    with ThreadPoolExecutor(cfg["run"]["concurrency"]) as pool:
        futures = [pool.submit(job, key, cfg, m, pr, r) for m, pr, r in jobs]
        for f in as_completed(futures):
            line = f.result()
            failed += line.startswith("FAIL")
            print(line, flush=True)
    print(f"done: {len(jobs)} calls, {failed} failed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
