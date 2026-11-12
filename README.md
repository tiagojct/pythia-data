# Pythia: data and scripts

Data and code for the essay *Pythia: Do machines agree on our future?* (Tiago Jacinto, 2026): https://tiagojacinto.eu/pythia/

24 language models, released from 2023 to 2026, each forecast the future of humanity to the year 10000. No model saw the answer of another. This repository holds every prompt, every raw response, the coding of the events and the analysis behind the numbers in the essay.

## Design

- Models: 24, called through OpenRouter in November 2026, grouped by the year of their release (2023: 2, 2024: 6, 2025: 6, 2026: 10). The list and the run settings are in `config.toml`.
- Prompts: two, in `prompts/`. `timeline.md` asks for a free timeline to 10000 (25 to 40 dated events) and whether humanity exists in 10000. `anchors.md` asks for the year and the probability of 28 fixed events (listed in `config.toml`), in an order that changes with the run number.
- Runs: 10 per model and prompt, temperature 1.0, no system prompt, no web search, no shared context. 480 calls, 478 usable.
- Coding: each of the 6,912 timeline events has a theme (21 themes), a valence and, where it says the same thing, one of the 28 fixed events (`coding/codebook.md`). Coder: claude-haiku-5.5. Second coder on 600 events: gpt-6-luna (`data/coded/agreement.md`). Hand check by the author: the first 70 rows of `data/coded/handcheck-result.csv`. Neither coder is one of the 24 models, and neither saw model names.
- Canonical events: claude-sonnet-5.5 proposed 87 events from a balanced sample of 1,145 (`coding/canonical.json`); claude-haiku-5.5 assigned every event to one of them or to "other".

## Files

| Path | Content |
|---|---|
| `data/raw/timeline/`, `data/raw/anchors/` | one JSON per call: the request, the full response, the time and the cost. Never edited. |
| `data/raw/anchors-v1/` | the first version of the anchor prompt, stopped because three events let models answer with a past year. Not used in the analysis. |
| `data/raw/excluded/` | runs left out, with the reason in its README. |
| `data/parsed/` | `runs.csv`, `timeline_events.csv`, `anchors.csv`, from `scripts/parse.py`. Repairs of the JSON are in the status and flags columns. |
| `data/coded/` | codes of both coders, agreement, canonical assignments, the hand check, and the raw coder responses. |
| `data/analysis/` | the tables and summaries cited in the essay. |
| `scripts/` | Python, standard library only. |

## Reproduce

Python 3.12 or later and [uv](https://docs.astral.sh/uv/).

```
uv run scripts/parse.py
uv run scripts/analyse_anchors.py
uv run scripts/analyse_timeline.py
uv run scripts/analyse_canonical.py
uv run scripts/plates.py
```

These steps read the files in this repository and need no network. New model calls or new coding (`scripts/run.py`, `scripts/code_timeline.py`, `scripts/canonical.py`) need an OpenRouter key in the environment variable `OPENROUTER_API_KEY`. They skip the calls that already have a file. A model id on OpenRouter can change its target, so new calls can give different data.

Conventions of the analysis, also in the docstring of `scripts/analyse_anchors.py`: one vote per model (the median of its runs); a null year ("not before 10000") counts as later than any year; the horizon is the forecast year minus the year the model believes it is now.

## Licence

Code: MIT (`LICENSE`). Prompts, codebook, codes and analysis: CC BY 4.0. The raw responses are the output of the models named in each file, shared for research and verification.

## Cite

Jacinto, T. (2026). *Pythia: Do machines agree on our future?* https://tiagojacinto.eu/pythia/
