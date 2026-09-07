# Backlog

Tasks for the Household Chores MVP, derived from [`plan.md`](plan.md)
and [`arch.md`](arch.md). Each task is scoped to be finishable in one
session and described completely enough to hand to someone who has not
read the others — refer to `plan.md`/`arch.md` for anything not
explained inline.

## 1. Project skeleton with a passing test
Goal: An empty Django project runs locally and has one passing automated test.
Description: Create the Django project per the layout in `arch.md` §3 (`config/` settings split into `base.py`/`dev.py`/`prod.py`, `pyproject.toml` with `uv`, `ruff` configured). Wire up `pytest` + `pytest-django` and add a single trivial test (e.g. Django check / a "homepage returns 200" placeholder view) that passes. No real features yet — this task just proves the toolchain works end to end.

## 2. Household model and slug-based access
Goal: Visiting the site creates a new household and routes by an unguessable URL.
Description: Add the `households` app with a `Household` model (`slug`, `created_at`) as described in `arch.md` §2/§4. Visiting `/` with no household creates one and redirects to `/h/<slug>/`; visiting an existing `/h/<slug>/` loads that household. No content on the page yet beyond confirming which household is loaded.

## 3. Partner model and first-launch naming
Goal: A household can have two named partners, entered on first visit.
Description: Add a `Partner` model (`household` FK, `name`) to the `households` app. When a household has no partners yet, show a simple form asking for both partner names; submitting creates exactly two `Partner` rows and proceeds to the (still mostly empty) household page. See `plan.md` §2.

## 4. "Acting as" partner switch
Goal: A visitor can choose which partner they currently are, and it's remembered.
Description: Once a household has two partners, show a control to select "acting as <name>"; store the choice in the session (scoped to that household). This selection is what later tasks use to attribute chore creation/completion — implement only the selection and storage here, not any chore behavior.

## 5. Base template and top-level navigation
Goal: All pages share one visual shell with working navigation.
Description: Build `templates/base.html` per `arch.md` §5/§6 (Tailwind included, centered layout, no multi-column desktop variant) with a nav bar linking **Household**, **Categories**, **Settings** (`plan.md` §8). The three destinations can be near-empty placeholder pages for now — this task is about the shared shell and nav wiring, not their content.

## 6. Category model and predefined seeding
Goal: Every new household starts with a fixed set of categories.
Description: Add the `categories` app with a `Category` model (`household` FK, `name`, `is_predefined`) per `arch.md` §4. When a `Household` is created, seed it with a fixed predefined list (define the list itself in this task). No UI yet beyond a bare page listing the seeded categories.

## 7. Custom category management
Goal: Either partner can add, rename, or delete their own categories.
Description: On the Categories page, add forms/actions to create a custom `Category`, rename any category, and delete a custom one (predefined categories cannot be deleted/renamed — decide and document that rule if not already fixed). Keep this to plain forms; HTMX polish can come later if time allows, but is not required for this task.

## 8. Chore model (fields only, no recurrence)
Goal: A `Chore` can be created, stored, and retrieved with its core fields.
Description: Add the `chores` app with a `Chore` model per `arch.md` §4, excluding recurrence: `title`, `description`, `owner` (FK to `Partner`), `category` (FK, optional), `due_date` (optional), `created_by`, `status` (active/completed). No views yet — this task is the model, its constraints, and model-level tests only.

## 9. Quick-add chore modal
Goal: Either partner can create a chore from the Household page in a couple of clicks.
Description: Implement the "quick add" flow from `plan.md` §5: a modal with just a title field by default, with an expandable section for description, owner, due date, and category. Submitting creates a `Chore` owned by the selected partner. Recurrence fields are out of scope for this task.

## 10. Household list view: display and ordering
Goal: The Household page shows all active chores for both partners, correctly ordered.
Description: Build the main Household view listing active chores from both partners in one shared list (not columns), each showing its owner, ordered by owner then due date (`plan.md` §4). Include the "All done 🎉" empty state with an Add Chore action when there are no active chores.

## 11. Overdue marking
Goal: Chores past their due date are visibly flagged in the list.
Description: In the Household list built in task 10, add an "Overdue" visual marker for any active chore whose `due_date` has passed. Overdue chores stay in the normal list position (ordered by owner, then due date) — they are not moved to a separate section.

## 12. Chore details/edit modal with permissions
Goal: Clicking a chore opens a modal to view and edit it, respecting who may delete.
Description: Clicking a chore in the Household list opens a modal showing its full details and an edit form (all fields from task 8). Either partner may save edits; only the chore's `created_by` partner sees/can use a delete action (`plan.md` §3). Enforce the delete restriction server-side, not just by hiding the button.

## 13. Complete chore with Undo
Goal: A chore can be marked done in one action, with a short window to undo it.
Description: Add a "Done" action on each chore that immediately sets it to completed (`plan.md` §5), attributed to the currently acting-as partner. Show a brief "Undo" affordance immediately after completion that reverts the chore to active if used in time; once the window passes (or the user navigates away), the completion stands.

## 14. Optional completion note
Goal: After completing a chore, a partner can attach a short note to that completion.
Description: Immediately after the "Done" action from task 13, offer an optional "Add note" step that attaches free-text to that specific completion record. Skipping it is the default path and must not block or delay the completion itself.

## 15. Completed section with history
Goal: Completed chores are visible in a collapsible section showing who completed them and when.
Description: Add a `ChoreHistory`-style record (or reuse fields on `Chore` if simpler — decide and document) written whenever a chore is completed, capturing who and when (and the optional note from task 14). Render a collapsible "Completed" section below the active list on the Household page (`plan.md` §5) listing recent completions.

## 16. Fixed-schedule recurrence
Goal: A chore can be set to recur daily, weekly, or monthly on a fixed schedule.
Description: Add the `Recurrence` model and UI for the three fixed-schedule kinds from `plan.md` §6: daily, weekly (specific weekday), and monthly (specific date or relative day such as "first Saturday"). This task covers defining and editing the recurrence rule on a chore; generating the next occurrence is handled in task 18.

## 17. Completion-based interval recurrence
Goal: A chore can be set to recur a fixed number of days/weeks after each completion.
Description: Extend the `Recurrence` model/UI from task 16 to support the four preset completion-based intervals from `plan.md` §6: 3 days, 1 week, 2 weeks, 1 month. A chore has exactly one recurrence rule at a time, of either the fixed-schedule or interval-based kind.

## 18. Generate next occurrence on completion
Goal: Completing a recurring chore automatically creates its next occurrence.
Description: When a chore with a `Recurrence` (from task 16 or 17) is completed, compute its next due date and create a new active `Chore` occurrence with the same owner and recurrence rule, per `arch.md` §4. The completed instance becomes history (task 15); it does not remain visible as active. Cover the date-math edge cases (e.g. month-end dates, "first Saturday" crossing a month boundary) with tests.

## 19. Editing recurrence updates current and future occurrences
Goal: Changing a recurring chore's schedule applies consistently going forward.
Description: When a partner edits the recurrence rule on an existing chore (`plan.md` §6), apply the change to the current active occurrence and ensure the next-generated occurrence (task 18) uses the updated rule, without altering already-completed history.

## 20. Settings: rename partners
Goal: Either partner can rename either partner from the Settings page.
Description: Build the Settings page section (`plan.md` §8) with a form to rename either of the two partners on the household. Renaming updates the display name everywhere (chore ownership, history) without changing which underlying `Partner` record things point to.

## 21. Settings: reset household data
Goal: A partner can clear household data with control over what gets cleared.
Description: Add a "reset data" action on the Settings page that asks what to clear (e.g. chores, categories, completion history) rather than wiping everything unconditionally (`plan.md` §8). Implement the confirmation step and the actual deletion logic for the options offered.

## 22. Deploy to Railway
Goal: The app runs on Railway against a real Postgres database.
Description: Following `arch.md` §9, add the `Procfile`, `railway.json` if needed, and production settings (`config/settings/prod.py`) so the app deploys on Railway with the Postgres plugin attached, migrations run as a release step, and static files served via WhiteNoise. Verify a fresh deploy serves the working app end to end.

## 23. CI pipeline
Goal: Every push and pull request is automatically linted and tested.
Description: Add a GitHub Actions workflow per `arch.md` §11 that installs dependencies with `uv`, runs `ruff check`, and runs the `pytest` suite on every push/PR. The workflow must fail the build on lint or test failures.
