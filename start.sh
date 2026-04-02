#!/bin/sh
if [ "$SERVICE_TYPE" = "worker" ]; then
  exec python -m app.worker.run
else
  alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port "$PORT"
fi
