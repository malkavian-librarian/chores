# Process

How work on this repo is tracked and how to pick up a task, for anyone (or any agent) joining cold.

## Where tasks live

Tasks are **GitHub issues**, not `_docs/tasks.md` (that file is the original backlog draft — the issues in the repo are the source of truth going forward; if the two ever disagree, the issue wins).

Repo: [`malkavian-librarian/chores`](https://github.com/malkavian-librarian/chores) — see the [Issues tab](https://github.com/malkavian-librarian/chores/issues).

Each issue follows the same shape:

- **Goal** — one-line summary of the outcome
- **Description** — 3-5 sentences of context on the work needed
- **Acceptance Criteria** — a checklist of everything that must be true for the task to be done

## Roles

- PM - grooms a task before anyone implements it, follows _docs/team/pm.md
- Engineer - implements one groomed task, follows _docs/team/software-engineer.md
- QA - checks the result against the acceptance criteria, follows _docs/team/qa-engineer.md

## Orchestrator

The main session is the orchestrator. It launches the PM, the engineer
and QA as subagents. It does not groom, implement or test itself.

Lifecycle

1. Pick the next open issue from the backlog
2. PM grooms it
3. Engineer implements it
4. QA verifies it
5. On FAIL, back to step 3 with the QA comment as input
6. On PASS, close the issue
7. Repeat until the backlog is empty

Rules

- Do not skip step 2
- The engineer does not close the issue
- QA does not fix the code, only outputs PASS or FAIL
- The orchestrator closes the issue only after QA outputs PASS

## How to work an issue

Work **one issue at a time**, start to finish, before picking up the next one.

1. **Read the acceptance criteria before starting.** They're the actual spec for the task — more precise than the description. If something in the description conflicts with an acceptance criterion, the criterion wins. If the criteria seem to require something out of scope for this task (e.g. touching another app/model), stop and flag it rather than silently expanding scope.
2. Check `_docs/arch.md` and `_docs/plan.md` (see below) for any context the issue references but doesn't repeat.
3. Implement the task. Don't implement ahead of the current issue — later issues assume earlier ones landed, not the reverse.
4. **Read the acceptance criteria again before closing.** Go down the checklist item by item and confirm each one is actually true (tests pass, the behavior is verified, not just "probably fine"). Check off each box in the issue as you confirm it.
5. Close the issue only once every box is checked. If a criterion turns out to be wrong or no longer applicable, say so in the issue rather than quietly checking it off.

## Commit regularly

Commit as you complete meaningful chunks of a task — not one giant commit at the end of an issue. Each commit should leave the repo in a working state (tests passing). Reference the issue number in the commit message (e.g. `Add Household model and slug routing (#2)`) so history stays traceable back to the issue.

## Other files in `_docs/`

| File | Purpose |
|---|---|
| `arch.md` | Architecture reference — stack choices (Django + HTMX + Postgres on Railway), app layout, data model, HTMX/template conventions, coding standards, deployment notes. Read this to understand *how it's built*. |
| `plan.md` | Product spec — what the app does, section by section (chore model, household view, creating/completing chores, recurrence, categories, settings). Read this to understand *behavior*. |
| `team/pm.md`, `team/software-engineer.md`, `team/qa-engineer.md` | Role instructions for the PM, engineer, and QA subagents (see Roles above). |
| `task-template.md` | The four-section template (Goal, Acceptance Criteria, Out of Scope, Constraints) every groomed issue follows. |
| `design-system.md` *(not yet created)* | Will define shared Tailwind/UI conventions (spacing, typography, the "warm and domestic" direction from `plan.md` §10) so the interface doesn't drift session to session. Until it exists, match whatever visual patterns already exist in the templates rather than inventing new ones per task. |
| `testing-guidelines.md` *(not yet created)* | Will describe how tests are structured beyond `arch.md` §7 (pytest-django, model/service-heavy, one test per view/HTMX endpoint). Until it exists, follow `arch.md` §7 and each issue's own acceptance criteria. |
| `tasks.md` | The original backlog draft the GitHub issues were generated from. Superseded by the issues themselves (see above) — kept for historical reference, don't treat it as current status. |
| `process.md` | This file. |

If one of the not-yet-created files above would materially help with a task and doesn't exist yet, flag it rather than guessing at conventions — creating it may be worth its own issue.
