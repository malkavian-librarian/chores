# chores

A shared household chore manager MVP for couples — a single-browser,
single-device prototype for dividing chores, tracking completion, and
managing recurring household routines.

No accounts, no backend, no sync: all data lives in browser
`localStorage`.

See [`_docs/plan.md`](_docs/plan.md) for the full product plan.

## Getting started

Requires Python 3.12 and [uv](https://docs.astral.sh/uv/).

```
uv sync
```

Runs against SQLite by default — no `DATABASE_URL` or Postgres needed
for local development (see `_docs/arch.md` §1/§8).

```
$env:DJANGO_SETTINGS_MODULE = "config.settings.dev"
uv run python manage.py migrate
uv run python manage.py runserver
```

Run the test suite:

```
uv run pytest
```
