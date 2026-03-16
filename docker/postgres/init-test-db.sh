#!/bin/bash
# Create the integration test database (separate from the app database).
# Postgres runs this on first volume init from /docker-entrypoint-initdb.d/.
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE DATABASE noa_test OWNER $POSTGRES_USER;
EOSQL
