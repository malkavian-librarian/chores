# Architecture & Engineering Guidelines

This document defines how the Household Chores MVP is built: the stack,
project layout, conventions, and standards. It implements **Option A**
from the tech-stack discussion — Django with server-rendered templates
and HTMX, backed by Postgres, deployed on Railway. See
[`plan.md`](plan.md) for product scope.

This is the source of truth for "how we build." When in doubt, follow
this document; propose a change here before deviating from it.

## 1. Tech Stack

| Layer            | Choice                                            |
|-------------------|---------------------------------------------------|
| Language          | Python 3.12                                        |
| Framework         | Django 5.x                                         |
| Interactivity     | HTMX 1.x (+ minimal vanilla JS where HTMX can't reach) |
| Styling           | Tailwind CSS (via `django-tailwind` or CLI build, no JS framework) |
| Database          | PostgreSQL (Railway managed Postgres plugin)       |
| Dev database      | Postgres via Docker, or SQLite fallback for quick local runs |
| Static files      | WhiteNoise (served by the app; no separate CDN for MVP) |
| Package manager   | `uv` (preferred) or `pip` + `venv`                 |
| App server        | Gunicorn                                           |
| Hosting           | Railway (single service, Nixpacks/buildpack auto-detect) |
| Task runner       | `make` or plain `manage.py` commands (no Celery — no background jobs in MVP) |

No REST API, no SPA framework, no auth framework (no accounts in MVP —
see plan.md section 9). No Redis, no Celery, no websockets. Keep the
stack boring and small; every dependency added beyond this list needs a
reason.

## 2. Household Identity (no accounts)

The plan explicitly rules out authentication and invite links, but this
app is now server-hosted rather than localStorage-only, so we need a
minimal stand-in for "which household is this":

- A **Household** is created implicitly on first visit to `/`.
- The household is identified by an unguessable slug in the URL:
  `/h/<household_slug>/`.
- The slug is generated server-side (e.g. `secrets.token_urlsafe(9)`)
  and stored in the visitor's session **and** is the URL itself, so
  either partner can bookmark/share the link to load the same household
  from another device or browser.
- No password, no login form, no `User` model tied to auth. Partner
  identity ("who am I acting as") is a simple session-stored choice
  between the two partner names on that household, re-selectable at any
  time (mirrors "select which partner they are acting as" from the
  plan).
- `/` with no slug redirects to a freshly created household.

This keeps the "no accounts, no invitations" spirit while fixing the
single-browser limitation that only existed because the original plan
assumed no backend.

## 3. Project Layout

Single Django project, apps split by domain concept, not by layer:

```
chores/
├── manage.py
├── pyproject.toml            # deps managed via uv
├── Procfile                  # Railway process definition
├── railway.json               # optional explicit build/deploy config
├── .env.example
├── config/                    # Django project package (settings, urls, wsgi)
│   ├── settings/
│   │   ├── base.py
│   │   ├── dev.py
│   │   └── prod.py
│   ├── urls.py
│   └── wsgi.py
├── households/                 # Household model, slug routing, partner session logic
├── chores/                     # Chore model, list view, create/edit/complete, recurrence
├── categories/                 # Category model, CRUD
├── core/                       # shared template tags, base template, mixins, utils
├── static/
├── templates/
└── tests/                      # or per-app tests/ dirs — see §7
```

Rules:

- One Django app per bounded concept from the plan (household,
  chore, category). Do not create a generic `api/` or `utils/` app that
  becomes a dumping ground — shared helpers live in `core/`.
- Views are function-based unless a class-based view removes real
  duplication (e.g. a shared modal-form pattern). Prefer boring and
  explicit over clever.
- No `models.py` file should import from another app's `views.py`.
  Cross-app dependencies flow through models and plain Python functions
  in a `services.py`, not views importing views.

## 4. Data Model

Directly from `plan.md` §3, §6, §7. Fields are the contract — do not
add fields not implied by the plan without updating it first.

- **Household** — `slug` (unique, indexed), `created_at`.
- **Partner** — `household` (FK), `name`. Exactly two per household,
  created together on first-launch onboarding.
- **Category** — `household` (FK), `name`, `is_predefined` (bool).
  Predefined categories are seeded per household on creation from a
  fixed list; either partner can add/rename/delete custom ones.
- **Chore** — `household` (FK), `title`, `description` (optional),
  `owner` (FK to Partner), `category` (FK, optional), `due_date`
  (optional), `recurrence` (nullable FK or JSON — see below),
  `created_by` (FK to Partner, for delete-permission checks),
  `status` (`active` / `completed`), `completed_at`, `completed_by`.
- **Recurrence** — modeled as its own small table (not a JSON blob) so
  "editing recurrence updates current + future occurrences" (plan §6)
  is a straightforward query, not JSON surgery:
  - `kind`: `fixed_daily` / `fixed_weekly` / `fixed_monthly_date` /
    `fixed_monthly_relative` / `interval_after_completion`.
  - `weekday`, `month_day`, `month_ordinal` + `month_weekday` (for
    "first Saturday"), `interval_days` — populated according to
    `kind`, the rest null.
- **ChoreHistory** — append-only log written on completion: `chore`,
  `completed_by`, `completed_at`, `note` (optional). This is what
  powers the "Completed" section and its history (plan §5).

Business rules to encode at the model/service layer, not just in
templates:

- Only `chore.created_by` may delete; either partner may edit
  (enforce in the view, not just hide the button).
- Completing a chore with an active recurrence creates the next
  occurrence (new `Chore` row) computed from `Recurrence`, rather than
  mutating `due_date` in place — keeps history honest.
- Deleting/editing a `Category` in use does not delete chores; category
  becomes null or reassigns per a single documented rule (decide before
  implementing categories, record the decision here once made).

## 5. Views, Templates & HTMX Conventions

- **Server renders HTML.** HTMX handles partial swaps; there is no
  client-side routing or state store. If a piece of UI needs local
  state beyond what HTMX + a form gives you, that's a signal to
  reconsider before reaching for JS.
- Every HTMX endpoint has a plain (non-HTMX) fallback: full-page render
  on direct GET, partial render when `HX-Request` header is present.
  Prefer Django's `django-htmx` package to check this cleanly
  (`request.htmx`).
- Template structure:
  - `templates/base.html` — shell, nav (Household / Categories /
    Settings per plan §8).
  - `templates/<app>/<view>.html` — full-page templates, each
    `{% extends "base.html" %}`.
  - `templates/<app>/partials/_<thing>.html` — fragments returned to
    HTMX swaps (e.g. `_chore_row.html`, `_chore_modal.html`). Prefix
    with `_` so partials are visually distinct from full pages at a
    glance.
- The "quick add" modal, Done/Undo, and edit-in-modal flows are each an
  HTMX endpoint returning a partial, not a full page reload.
- Undo (plan §5) is implemented as a short-lived server-side action:
  completing sets `status=completed`; Undo (available for e.g. 8
  seconds via a client-side timer showing/hiding an Undo button) posts
  back to revert `status=active` and delete the just-created next
  occurrence if one was generated. No optimistic client state to
  reconcile.
- Keep templates presentation-only. Sorting (owner, then due date),
  overdue detection, and "all done" empty-state logic live in the view
  or a `services.py`, exposed to the template as already-prepared
  context — templates should not contain business logic beyond `{% if
  %}` on a precomputed flag.

## 6. Styling / UX

- Tailwind CSS utility classes directly in templates. No component
  library, no custom design system for the MVP — plan §10 calls for
  "warm and domestic," which is a content/typography/color decision,
  not a framework decision.
- One shared centered list layout at all breakpoints (plan §4 — no
  multi-column desktop layout). Avoid building responsive complexity
  that the plan explicitly says not to build.
- Keep custom CSS in a single `static/css/app.css` (Tailwind entry
  point) — no per-component stylesheets.

## 7. Testing

- `pytest` + `pytest-django`. No `unittest.TestCase` style — keep one
  convention.
- Test pyramid for this app is model/service-heavy, view-light:
  - **Model/service tests**: recurrence date math, permission rules
    (who can edit/delete), history writing on completion — these are
    the parts most likely to have subtle bugs and are cheap to test
    without a browser.
  - **View tests** (Django test client, not a browser): one happy-path
    test per view/HTMX endpoint (renders 200, correct template used,
    correct partial on `HX-Request`).
  - No end-to-end/browser tests for the MVP — not worth the
    infrastructure at this scope.
- Every new model field or recurrence `kind` ships with a test for its
  date-math edge case (e.g. "first Saturday" crossing a month
  boundary, monthly-date recurrence landing on the 31st of a
  30-day month).
- Tests live in `<app>/tests/test_<thing>.py`, one file per
  model/view/service, not one giant `tests.py` per app.

## 8. Settings & Environment

- Split settings: `config/settings/base.py` (shared),
  `dev.py`, `prod.py`. `DJANGO_SETTINGS_MODULE` selects which; Railway
  sets it to `config.settings.prod`.
- All secrets/environment-specific values come from environment
  variables via `django-environ` (or `os.environ` directly — pick one,
  don't mix). `.env` for local dev, never committed (`.env.local`
  already ignored — see root `.gitignore`); `.env.example` documents
  every variable with a placeholder value.
- Required env vars: `DATABASE_URL`, `SECRET_KEY`, `DEBUG`,
  `ALLOWED_HOSTS`. Railway injects `DATABASE_URL` automatically when
  the Postgres plugin is attached.
- `DEBUG=False` in `prod.py` unconditionally (not env-gated) — never
  ship a code path that can run production with `DEBUG=True` by
  misconfigured env var.

## 9. Deployment (Railway)

- One Railway service running the Django app via Gunicorn:
  `gunicorn config.wsgi --bind 0.0.0.0:$PORT`.
- One Railway Postgres plugin attached, providing `DATABASE_URL`.
- Migrations run as a Railway **release step** (pre-deploy command:
  `python manage.py migrate`), not manually and not on every request.
- Static files collected at build time (`python manage.py
  collectstatic --noinput`) and served via WhiteNoise — no separate
  static host/CDN for the MVP.
- `Procfile`:
  ```
  release: python manage.py migrate
  web: gunicorn config.wsgi --bind 0.0.0.0:$PORT
  ```
- No staging environment for the MVP — Railway's PR/preview
  environments (if enabled) stand in for one. Production is the `main`
  branch, deployed on push.

## 10. Code Style & Conventions

- Formatting/linting: `ruff` (format + lint) with default rules plus
  Django-aware import ordering. Run in CI (see §11) and pre-commit if a
  hook is set up.
- Type hints on function signatures in `services.py` and model methods;
  not required in views/templates-adjacent glue code.
- Naming: Django app names are plural nouns matching the plan's
  vocabulary (`chores`, `categories`, `households`) — no renaming to
  generic terms like `tasks` or `items`.
- No commented-out code, no `# TODO` without a linked task (see
  `task-template.md`) — open a task instead.
- Migrations are committed and never edited after being merged to
  `main`; a mistake gets a new migration, not a rewritten one (Railway
  runs migrations against a real persistent database).

## 11. CI

- GitHub Actions workflow on every push/PR: install deps (`uv sync`),
  run `ruff check`, run `pytest`.
- No deploy step in CI — Railway deploys independently on push to
  `main` via its GitHub integration.

## 12. Explicitly Out of Scope (architecture-level)

Mirrors plan.md §11, translated to engineering terms — do not add:

- Django's built-in auth app / `User` model / login views.
- REST API endpoints or DRF — this is server-rendered HTML only.
- Celery, Redis, background workers, or scheduled jobs (recurrence
  "next occurrence" is generated synchronously on completion, not by a
  cron job).
- A JS framework (React/Vue/etc.) or client-side state management.
- Multi-tenancy beyond the simple `household_slug` URL scheme in §2.
- A CDN or object storage — no file/photo uploads in the MVP.

## 13. Open Decisions

Track anything not yet settled here until resolved, then move the
resolution into the relevant section above:

- Exact behavior when a `Category` in use is deleted (null out vs.
  reassign) — see §4.
- Whether the "first launch" onboarding (partner names → first chore)
  is a dedicated view/wizard or folded into the empty-household state
  of the main Household view.
