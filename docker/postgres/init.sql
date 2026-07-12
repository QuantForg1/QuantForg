# QuantForg — PostgreSQL initialization script
-- Runs once on first container start via docker-entrypoint-initdb.d

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Application role privileges are managed by the POSTGRES_USER env var.
-- Schema migrations are handled exclusively by Alembic.
