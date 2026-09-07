"""Shared views for the project.

No domain features live here — see `households`, `chores`, and
`categories` apps for real functionality. Per `_docs/arch.md` §3, this
app holds shared template tags, base template, mixins, and utils, not
routes of its own; the root URL is owned by `households` (see issue #2).
"""
