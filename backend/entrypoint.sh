#!/bin/sh
set -e

python apply_migrations.py
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers "${INFERENCE_WORKERS:-1}" --no-access-log
