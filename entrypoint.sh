#!/bin/sh
set -e

# Set defaults
PUID=${PUID:-1000}
PGID=${PGID:-1000}

echo "Setting up user with PUID=${PUID} and PGID=${PGID}..."

# Create group and user with specified IDs
groupadd -g "${PGID}" app 2>/dev/null || true
useradd -u "${PUID}" -g "${PGID}" -s /bin/sh app 2>/dev/null || true

# Fix ownership of application files
echo "Fixing file permissions..."
chown -R app:app /app

echo "Starting LPRD Plugin..."
exec gosu app:app python -m uvicorn app.main:app --host 0.0.0.0 --log-level info --no-access-log