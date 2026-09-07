# Shared Household Chores --- MVP Plan

## 1. Product Goal

Build a simple shared household chore manager for couples. The product
should help two partners:

-   divide chores clearly;
-   make sure chores get done;
-   establish recurring household routines.

The MVP focuses strictly on chore management rather than gamification,
relationship features, or productivity analytics.

## 2. Target Users

A household consisting of **two partners**.

The MVP is a **single-browser, single-device prototype**. There are no
accounts, authentication, or real invitations. On first launch, users
enter both partner names and can then select which partner they are
acting as.

## 3. Core Chore Model

Each chore has:

-   title;
-   optional description;
-   owner;
-   optional due date;
-   optional recurrence;
-   optional category.

Ownership is fixed to one partner. A chore may be reassigned before it
has been completed. Either partner may edit a chore, but only its
creator may delete it.

All chores are treated equally: there are no points, effort estimates,
or weighting.

## 4. Household View

The main screen is a shared **Household** list containing both partners'
chores.

-   One shared list rather than separate columns.
-   Chores show their owner.
-   Default ordering is by **owner, then due date**.
-   No filters or search in the MVP.
-   Overdue chores remain in the list and are visibly marked
    **Overdue**.
-   Clicking a chore opens an edit/details modal.
-   When no active chores remain, show **"All done 🎉"** and an **Add
    Chore** action.

Desktop keeps the same centered list rather than introducing a
multi-column layout.

## 5. Creating & Completing Chores

Either partner can create and assign chores to either person.

Adding a chore uses a quick modal:

1.  Enter the title.
2.  Optionally expand the form for description, owner, due date,
    recurrence, and category.

On first launch, after entering both partner names, the app prompts
users to create their first chore using this same flow.

Completing a chore is a single **Done** action. Completion is immediate,
followed by an optional **Add note** action. A brief **Undo** action is
available after completion.

Completed chores appear in a collapsible **Completed** section below the
active household list. History records who completed the chore and when.

## 6. Recurring Chores

The app supports both:

-   **fixed schedules**; and
-   **intervals after completion**.

### Fixed schedules

Support:

-   Daily
-   Weekly --- with a specific weekday
-   Monthly --- either a specific date or relative day such as "first
    Saturday"

### Completion-based intervals

Preset options:

-   3 days
-   1 week
-   2 weeks
-   1 month

Recurring chores retain the same owner.

When completed, the completion enters history. A new occurrence is
generated when the next due date arrives rather than remaining
permanently visible.

Editing recurrence updates both the current active occurrence and future
occurrences.

## 7. Categories

Provide predefined categories and allow users to create custom ones.

Either partner can create, rename, or delete custom categories.

For the MVP, categories are primarily visual labels. The data model
should leave room for category-based filtering later, but filtering
itself is not part of the MVP.

## 8. Navigation & Settings

Top-level navigation:

-   **Household**
-   **Categories**
-   **Settings**

Settings allow users to:

-   rename either partner;
-   reset household data.

Resetting data asks what should be cleared rather than automatically
deleting everything.

## 9. Platform & Persistence

Build as a **responsive web application**.

All data is stored in browser **localStorage**.

Consequences accepted for this MVP:

-   data does not synchronize between devices;
-   both partners use the same browser/device;
-   no backend is required;
-   no authentication;
-   no invite links.

## 10. UX Direction

The interface should feel **warm and domestic** rather than like a
corporate task manager.

Keep interaction simple and lightweight, with the shared household list
as the center of the experience.

## 11. Explicitly Out of Scope

The MVP does **not** include:

-   authentication or user accounts;
-   invitation links;
-   multi-device synchronization;
-   backend/database;
-   notifications or reminders;
-   chore search;
-   chore filters;
-   effort estimates, points, or fairness metrics;
-   gamification or streaks;
-   reactions or relationship features;
-   partner approval of completed chores;
-   completion photos/proof;
-   implementation task breakdown.

## 12. MVP Success

The prototype is successful if two partners using the same browser can
set themselves up, create and assign chores, manage recurring routines,
see what each person is responsible for, complete chores, and review
recent completions without additional coordination features.
