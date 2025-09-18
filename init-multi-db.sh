#!/bin/bash
set -e

echo "🚀 Starting database initialization..."

# Connect to the default 'postgres' database to manage other databases
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "postgres" <<-EOSQL
    -- Drop databases if they exist to ensure a clean setup
    DROP DATABASE IF EXISTS users;
    DROP DATABASE IF EXISTS tokens; -- Removing the old 'tokens' DB
    DROP DATABASE IF EXISTS chatlogs;

    -- Create the two fresh databases required by the services
    CREATE DATABASE users;
    CREATE DATABASE chatlogs;
EOSQL

echo "✅ Databases 'users' and 'chatlogs' created successfully."
echo "ℹ️ Table schemas will be created by the backend and consumer services on startup."