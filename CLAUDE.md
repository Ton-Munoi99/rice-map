# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Architecture, commands and hard constraints live in `AGENTS.md` — read it before making changes.
This file only adds what `AGENTS.md` does not cover.

## Current state

`HANDOFF.md` is mostly a dated log. Read the newest entry under `## Log` and the
`## Deferred Decisions` section, not the whole file. Add a new top entry to the log before
handing the repository back to another coding agent.

## Checking your work

There is no test runner. Pipeline logic is guarded by assert-based self-tests; run the one for
any script you touch (CI also runs each before its script's cron fetch, so a broken change fails
the workflow instead of overwriting data):

```bash
python scripts/fetch_agri_warnings.py --selftest
python scripts/fetch_flood_status.py --selftest
python scripts/fetch_weather_forecast.py --selftest
```

`python scripts/check_data_freshness.py` reports stale `data/*.json` by commit age. It cannot see
a file that is committed on schedule with wrong contents — see the "say it in the data, then
assert it" constraint in `AGENTS.md`.

UI changes are verified in the browser through the real click path (`setLayer()` via the layer
buttons), never by assigning `S` directly, which skips the reset logic.

## Git

- `main` receives ~20 cron pushes a day. Push only with `bash scripts/push-verified.sh`, and only
  after the owner says so.
- Record every change in `CHANGELOG.md` (Thai, current month section).
