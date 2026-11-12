"""Parse the raw pythia responses into flat CSV files.

Usage:
    uv run scripts/parse.py

Reads data/raw/<prompt>/<model>/run-NN.json. Writes data/parsed/:
    runs.csv             one row per call: status, metadata, tokens, cost
    timeline_events.csv  one row per timeline event
    anchors.csv          one row per anchor forecast (all anchors for each parsed run;
                         an anchor the model left out has status "missing")

Raw files are only read. Each value that needs a repair gets a flag, so the
analysis can include or exclude it.
"""

import csv
import difflib
import json
import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "parsed"

# ---------------------------------------------------------------- JSON extraction


def extract_json(text: str) -> tuple[dict | None, list[str]]:
    """Return the first JSON object in text, and the repairs that were needed."""
    flags = []
    s = text.strip()
    if not s:
        return None, ["empty"]

    fence = re.search(r"```(?:json)?\s*(.*?)```", s, re.S)
    if fence:
        s = fence.group(1).strip()
        flags.append("fenced")

    try:
        obj = json.loads(s)
        return (obj, flags) if isinstance(obj, dict) else (None, flags + ["not_object"])
    except json.JSONDecodeError:
        pass

    start = s.find("{")
    if start == -1:
        return None, flags + ["no_json"]
    if start > 0:
        flags.append("text_before")

    # Each repair builds on the one before. The flag names the last one needed.
    body = s[start:]
    basic = re.sub(r"//[^\n\"]*\n", "\n", body)
    basic = re.sub(r",\s*([}\]])", r"\1", basic)
    quotes = escape_inner_quotes(basic)
    closed = close_open(quotes)
    candidates = [
        (body, None),
        (basic, "repaired_commas"),
        (quotes, "repaired_inner_quotes"),
        (closed, "repaired_unclosed"),
    ]

    decoder = json.JSONDecoder()
    for cand, flag in candidates:
        try:
            obj, end = decoder.raw_decode(cand)
        except json.JSONDecodeError:
            continue
        if not isinstance(obj, dict):
            continue
        if flag:
            flags.append(flag)
        if cand[end:].strip():
            flags.append("text_after")
        return obj, flags
    return None, flags + ["bad_json"]


VALUE_LINE = re.compile(r'^(\s*"[A-Za-z_0-9]+"\s*:\s*")(.*)("\s*,?\s*)$')


def escape_inner_quotes(s: str) -> str:
    """Escape bare quotes inside a string value that fills one line.

    Example: "event": "The "Long Silence" begins",
    """
    out = []
    for line in s.splitlines():
        m = VALUE_LINE.match(line)
        if m and re.search(r'(?<!\\)"', m.group(2)):
            inner = re.sub(r'(?<!\\)"', r'\\"', m.group(2))
            line = m.group(1) + inner + m.group(3)
        elif OPEN_VALUE.match(line):
            # "detail": "text with no closing quote
            line = line.rstrip() + '"'
        else:
            line = COMPACT_VALUE.sub(_escape_compact, line)
        out.append(line)
    return "\n".join(out)


# A value that opens and never closes on its line.
OPEN_VALUE = re.compile(r'^\s*"[A-Za-z_0-9]+"\s*:\s*"[^"]*$')
# Text values inside a one-line object: {"year": 2050, "event": "...", "detail": "..."}.
# The value ends at a quote followed by the next key or the closing brace.
COMPACT_VALUE = re.compile(r'("(?:event|detail|summary)"\s*:\s*")(.*?)("(?=\s*(?:,\s*"[A-Za-z_]+"\s*:|\})))')


def _escape_compact(m: re.Match) -> str:
    return m.group(1) + re.sub(r'(?<!\\)"', r'\\"', m.group(2)) + m.group(3)


def close_open(s: str) -> str:
    """Close a string, arrays and objects left open at the end (output that stops early)."""
    stack, in_str, esc = [], False, False
    for ch in s:
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
        elif ch == '"':
            in_str = True
        elif ch in "{[":
            stack.append("}" if ch == "{" else "]")
        elif ch in "}]" and stack:
            stack.pop()
    tail = '"' if in_str else ""
    out = (s + tail).rstrip().rstrip(",")
    return out + "".join(reversed(stack))


# ---------------------------------------------------------------- value cleaning


def to_year(v) -> tuple[int | None, str]:
    """Year as int. Returns (year, flag). flag is '' when the value was clean."""
    if v is None:
        return None, ""
    if isinstance(v, bool):
        return None, "bad_year"
    if isinstance(v, int):
        return v, ""
    if isinstance(v, float):
        return int(round(v)), "year_float"
    if isinstance(v, str):
        t = v.strip().lower()
        if t in ("", "null", "none", "never", "n/a", "na", "-"):
            return None, "year_text_null"
        m = re.search(r"-?\d{3,5}", t.replace(",", ""))
        if m:
            return int(m.group(0)), "year_text"
    return None, "bad_year"


def to_prob(v) -> tuple[float | None, str]:
    if v is None:
        return None, "no_probability"
    if isinstance(v, bool):
        return None, "bad_probability"
    flag = ""
    if isinstance(v, str):
        try:
            v = float(v.strip().rstrip("%"))
        except ValueError:
            return None, "bad_probability"
        flag = "probability_text"
    if isinstance(v, (int, float)):
        if 0 <= v <= 1:
            return float(v), flag
        if 1 < v <= 100:
            return v / 100, "probability_percent"
    return None, "bad_probability"


def norm_humanity(v) -> str:
    if v is None:
        return ""
    t = str(v).strip().lower().rstrip(".")
    if t.startswith("yes"):
        return "yes"
    if t.startswith("no"):
        return "no"
    if t.startswith("uncertain") or t.startswith("unknown"):
        return "uncertain"
    return "other"


# ---------------------------------------------------------------- per file


def usage_fields(resp: dict) -> dict:
    u = resp.get("usage") or {}
    det = u.get("completion_tokens_details") or {}
    return {
        "prompt_tokens": u.get("prompt_tokens"),
        "completion_tokens": u.get("completion_tokens"),
        "reasoning_tokens": det.get("reasoning_tokens"),
        "cost_usd": u.get("cost"),
    }


def parse_file(path: Path, anchor_ids: list[str]):
    rec = json.loads(path.read_text())
    resp = rec["response"]
    choice = resp["choices"][0]
    text = (choice.get("message") or {}).get("content") or ""
    finish = choice.get("finish_reason") or ""

    run = {
        "prompt": rec["prompt"],
        "model": rec["model"],
        "era": rec["era"],
        "run": rec["run"],
        "requested_at": rec["requested_at"],
        "seconds": rec["seconds"],
        "served_model": resp.get("model", ""),
        "provider": resp.get("provider", ""),
        "finish_reason": finish,
        **usage_fields(resp),
    }

    obj, flags = extract_json(text)
    if finish == "length":
        flags.append("truncated")
    if run["served_model"] and run["served_model"] != rec["model"]:
        flags.append("served_other_model")

    events, forecasts = [], []
    current_year, cy_flag = to_year((obj or {}).get("current_year"))
    if cy_flag:
        flags.append("current_year_" + cy_flag)

    if obj is None:
        status = "failed"
    elif rec["prompt"] == "timeline":
        status, events = parse_timeline(obj, run, current_year, flags)
    else:
        status, forecasts = parse_anchors(obj, run, current_year, rec.get("anchor_order"), anchor_ids, flags)

    run.update(
        status=status,
        flags=";".join(dict.fromkeys(flags)),
        current_year=current_year,
        chars=len(text),
    )
    return run, events, forecasts


def parse_timeline(obj, run, current_year, flags):
    raw_events = obj.get("events")
    if not isinstance(raw_events, list):
        flags.append("no_events")
        return "failed", []

    rows = []
    for i, e in enumerate(raw_events, 1):
        if not isinstance(e, dict):
            flags.append("bad_event")
            continue
        year, yflag = to_year(e.get("year"))
        rows.append({
            "model": run["model"], "era": run["era"], "run": run["run"],
            "order": i,
            "year": year,
            "event": str(e.get("event", "")).strip(),
            "detail": str(e.get("detail", "")).strip(),
            "flag": yflag,
        })
    years = [r["year"] for r in rows if r["year"] is not None]
    run.update(
        n_items=len(rows),
        min_year=min(years) if years else None,
        max_year=max(years) if years else None,
        humanity_10000=norm_humanity(obj.get("humanity_exists_in_10000")),
        summary=str(obj.get("summary", "")).strip(),
    )
    if len(rows) < 25:
        flags.append("under_25_events")
    if years and max(years) < 10000:
        flags.append("stops_before_10000")
    if any(r["flag"] == "bad_year" for r in rows):
        flags.append("bad_event_year")
    unsorted = any(a > b for a, b in zip(years, years[1:]))
    if unsorted:
        flags.append("events_not_sorted")
    return ("ok" if rows else "failed"), rows


def parse_anchors(obj, run, current_year, order, anchor_ids, flags):
    raw = obj.get("forecasts")
    if isinstance(raw, dict):  # {"agi": {...}} instead of a list
        raw = [{"id": k, **v} if isinstance(v, dict) else {"id": k, "year": v} for k, v in raw.items()]
        flags.append("forecasts_as_object")
    if not isinstance(raw, list):
        flags.append("no_forecasts")
        return "failed", []

    lookup = {a.lower(): a for a in anchor_ids}
    got: dict[str, dict] = {}
    for f in raw:
        if not isinstance(f, dict):
            continue
        key = str(f.get("id", "")).strip().strip("-: ").lower()
        aid = lookup.get(key)
        if aid is None:
            close = difflib.get_close_matches(key, list(lookup), n=1, cutoff=0.8)
            if not close:
                flags.append("unknown_id")
                continue
            aid = lookup[close[0]]
            flags.append(f"id_fuzzy:{key}->{aid}")
        if aid in got:
            flags.append("duplicate_id")
            continue
        got[aid] = f

    position = {a: i + 1 for i, a in enumerate(order or [])}
    rows = []
    for aid in anchor_ids:
        f = got.get(aid)
        row = {
            "model": run["model"], "era": run["era"], "run": run["run"],
            "id": aid, "position": position.get(aid),
            "year": None, "never": None, "past": None, "probability": None,
            "status": "missing", "flag": "",
        }
        if f is not None:
            year, yflag = to_year(f.get("year"))
            prob, pflag = to_prob(f.get("probability"))
            row.update(
                year=year,
                never=year is None and yflag in ("", "year_text_null"),
                past=(year is not None and current_year is not None and year <= current_year),
                probability=prob,
                status="ok",
                flag=";".join(x for x in (yflag, pflag) if x),
            )
            # A null year with a high probability contradicts itself.
            if row["never"] and prob is not None and prob >= 0.5:
                row["flag"] = ";".join(x for x in (row["flag"], "null_year_high_probability") if x)
        rows.append(row)

    n = len(got)
    run.update(n_items=n)
    if n < len(anchor_ids):
        flags.append(f"missing_{len(anchor_ids) - n}")
    status = "ok" if n == len(anchor_ids) else ("partial" if n else "failed")
    return status, rows


# ---------------------------------------------------------------- main

RUN_COLS = [
    "prompt", "model", "era", "run", "status", "flags", "current_year", "n_items",
    "min_year", "max_year", "humanity_10000", "summary",
    "finish_reason", "served_model", "provider", "requested_at", "seconds",
    "prompt_tokens", "completion_tokens", "reasoning_tokens", "cost_usd", "chars",
]
EVENT_COLS = ["model", "era", "run", "order", "year", "event", "detail", "flag"]
ANCHOR_COLS = ["model", "era", "run", "id", "position", "year", "never", "past",
               "probability", "status", "flag"]


def write_csv(path: Path, cols: list[str], rows: list[dict]) -> None:
    with path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: ("" if r.get(k) is None else r.get(k)) for k in cols})


def main() -> None:
    cfg = tomllib.loads((ROOT / "config.toml").read_text())
    anchor_ids = [a["id"] for a in cfg["anchors"]]
    era = {m["id"]: m["era"] for m in cfg["models"]}

    runs, events, anchors, unreadable = [], [], [], []
    # Only the current prompt folders. Old versions (anchors-v1) stay out.
    paths = sorted(p for name in ("timeline", "anchors") for p in (RAW / name).glob("*/run-*.json"))
    for path in paths:
        try:
            r, ev, an = parse_file(path, anchor_ids)
        except (json.JSONDecodeError, KeyError, IndexError) as e:
            unreadable.append(f"{path.relative_to(ROOT)}: {e!r}")
            continue
        if r["model"] not in era:
            r["flags"] = ";".join(x for x in (r["flags"], "not_in_config") if x)
        runs.append(r)
        events += ev
        anchors += an

    OUT.mkdir(parents=True, exist_ok=True)
    write_csv(OUT / "runs.csv", RUN_COLS, runs)
    write_csv(OUT / "timeline_events.csv", EVENT_COLS, events)
    write_csv(OUT / "anchors.csv", ANCHOR_COLS, anchors)

    # Summary: status counts for each model and prompt.
    table: dict[tuple, dict] = {}
    for r in runs:
        t = table.setdefault((r["model"], r["prompt"]), {})
        t[r["status"]] = t.get(r["status"], 0) + 1
    print(f"{'model':42} {'prompt':9} ok partial failed")
    for (m, p), t in sorted(table.items(), key=lambda x: (era.get(x[0][0], 0), x[0])):
        print(f"{m:42} {p:9} {t.get('ok', 0):2} {t.get('partial', 0):7} {t.get('failed', 0):6}")
    cost = sum(r["cost_usd"] or 0 for r in runs)
    print(f"\n{len(runs)} runs, {len(events)} timeline events, {len(anchors)} anchor rows, cost {cost:.2f} USD")
    for u in unreadable:
        print("unreadable:", u, file=sys.stderr)


if __name__ == "__main__":
    main()
