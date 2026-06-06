"""Background worker (Phase 9).

Long-running scheduler that performs the two jobs Reno-Budget needs outside
of the request/response cycle:

* **Nightly Postgres backup** — ``pg_dump`` into a gzipped ``.sql.gz`` file
  with daily + monthly retention. See :mod:`app.worker.backup`.
* **Weekly reminder digest** — collects per-user reminders (urgent cost
  items, Renofond underfunding, recent attachments by collaborators) and
  emails the user a single German summary. See :mod:`app.worker.digest`.

The entrypoint module :mod:`app.worker.main` wires APScheduler to those two
jobs and exposes a ``--run-once`` flag for manual execution.
"""

from __future__ import annotations
