"""Allow ``python -m app.worker`` to invoke :func:`app.worker.main.main`."""

from __future__ import annotations

from app.worker.main import main

if __name__ == "__main__":
    raise SystemExit(main())
