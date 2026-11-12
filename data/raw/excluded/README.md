# Excluded raw runs

These files are kept for reference. scripts/parse.py does not read this folder.

- timeline/ and anchors/mistralai__mistral-large-2407 (20 files, 2026-11-12): the dated id is served by Mistral as the current Mistral Large. Each call used 4,000 to 9,000 reasoning tokens, the same as mistral-large-4-0, so the data is not from the 2024 model. Replaced by mistralai/mixtral-8x22b-instruct (April 2024, no reasoning tokens, assumed year 2024 in a test call).
- anchors/moonshotai__kimi-k3.1-pro/run-10.json (2026-11-12): empty content, finish_reason "error" from the provider (PrimaLabs). A provider fault, not model behaviour. The call was repeated.
