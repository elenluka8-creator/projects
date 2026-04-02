#!/usr/bin/env bash
# scripts/init_db.sh
#
# Run Alembic migrations to bring the database schema up to date.
#
# Usage:
#   ./scripts/init_db.sh
#
# Requires DATABASE_URL to be set in the environment or in a .env file.
# The script will load .env automatically if it exists in the project root.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${PROJECT_ROOT}"

# Load .env if present (and if not already exported by the caller)
if [ -f ".env" ] && [ -z "${DATABASE_URL:-}" ]; then
    echo "Loading .env ..."
    set -a
    # shellcheck disable=SC1091
    source .env
    set +a
fi

if [ -z "${DATABASE_URL:-}" ]; then
    echo "ERROR: DATABASE_URL is not set." >&2
    echo "  Set it in your environment or copy .env.example to .env and fill it in." >&2
    exit 1
fi

echo "Running Alembic migrations against: ${DATABASE_URL%%@*}@***"
alembic upgrade head
echo "Migrations complete."
