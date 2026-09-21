# Contributor Guide

- Preserve the local-first and non-destructive guarantees in `README.md` and `DECISIONS.md`.
- Never move or delete a screenshot as part of ingestion, analysis, retry, or cleanup.
- Never log, persist, or commit API credentials.
- Keep the OpenAI-compatible provider configurable; do not hard-code a vendor model.
- Use `MockProvider` or a fake provider in tests. Automated tests must not call a paid or external AI API.
- Update `TASKS.md` when changing task scope or completion status.
- Run `python -m pytest`, `python -m ruff check .`, and `python -m mypy` before handoff.
