#!/bin/bash
# Startup script for knowledge base service that ensures enum types are properly set up

# Wait for PostgreSQL to be ready
echo "Waiting for PostgreSQL to be ready..."
until python -c "import os, psycopg2; conn = psycopg2.connect(host='kosmos-postgresql', port=5432, dbname='kosmos', user='kosmos', password=os.environ.get('POSTGRES_PASSWORD')); conn.close()" 2>/dev/null; do
    sleep 1
done
echo "PostgreSQL is ready."

# Run the enum type repair script first
echo "Running enum type repair script..."
python -m backend.scripts.repair_enum_types

# Run the database schema fix script
echo "Running database schema fix script..."
# Set PYTHONPATH to include the /app directory for module imports
export PYTHONPATH=/app:$PYTHONPATH

echo "Running enum type repair script..."
python /app/backend/scripts/repair_enum_types.py
echo "Running database schema fix script..."
python /app/scripts/fix_database_schema.py
echo "Starting the knowledge base service..."
exec uvicorn backend.app.main:app --host 0.0.0.0 --port 8011