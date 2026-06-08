#!/bin/sh
set -e

# Run alembic before serving so the schema matches the image we just deployed.
# Only the api container runs this; the worker reuses the same image but its
# CMD bypasses this entrypoint so we don't race for the migration lock.
if [ "${RENO_RUN_MIGRATIONS:-1}" = "1" ]; then
  echo "[entrypoint] alembic upgrade head"
  alembic upgrade head
fi

exec "$@"
