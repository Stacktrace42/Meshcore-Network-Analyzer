#!/bin/bash
set -e

echo "Running database initialization..."
python init_db.py

if [ $? -ne 0 ]; then
    echo "Database initialization failed!"
    exit 1
fi

echo "Starting application..."
exec uvicorn src.main:app --host 0.0.0.0 --port 8000
