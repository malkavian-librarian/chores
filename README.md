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

## Styling (Tailwind CSS)

Styling uses the Tailwind CLI (not `django-tailwind`, not the Tailwind
CDN script — see `_docs/arch.md` §6 and issue #4) to compile
`static/css/src/input.css` into `static/css/app.css`, referenced from
`templates/base.html` via `{% static "css/app.css" %}`. Requires
Node.js (for `npx`) only for this build step — the app itself has no
Node runtime dependency.

```
npm install
npx tailwindcss -i static/css/src/input.css -o static/css/app.css --watch
```

For a one-off production-style build:

```
npx tailwindcss -i static/css/src/input.css -o static/css/app.css --minify
```

The compiled `static/css/app.css` is committed for now, since there's
no build step wired into CI/deploy yet (`_docs/arch.md` §9 covers
`collectstatic`/WhiteNoise, not a Tailwind build step). Re-run the
build and commit the output whenever templates change classes.
