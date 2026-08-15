#!/bin/sh
# Docker creates a directory named jobs.db instead of a file when it doesn't exist
# on the host at the time of the volume mount. This entrypoint ensures it's a file.
if [ -d "/app/jobs.db" ]; then
    rmdir /app/jobs.db 2>/dev/null || true
fi
touch /app/jobs.db
exec python app.py
