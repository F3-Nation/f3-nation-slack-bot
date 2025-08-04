# Database Initialization Service

This directory contains the Docker setup for initializing the F3 Nation database schema.

## Files

- **`Dockerfile`**: Builds a container that clones F3-Data-Models and sets up Poetry
- **`entrypoint.sh`**: Script that handles database initialization:
  - Waits for PostgreSQL to be ready (5-second intervals)
  - Creates the database if it doesn't exist
  - Installs Poetry dependencies for the current session
  - Configures Python version for Poetry environment
  - Runs Alembic migrations to create all tables
  - Provides detailed logging throughout the process

## What it does

1. **Clones** the [F3-Data-Models repository](https://github.com/F3-Nation/F3-Data-Models) during build
2. **Installs** Poetry and base dependencies during build
3. **Waits** for the PostgreSQL database to be ready (5-second intervals)
4. **Creates** the F3 database if it doesn't exist
5. **Installs** current Poetry dependencies for migrations
6. **Configures** Python version for Poetry environment
7. **Runs** `alembic upgrade head` to create all tables and schema
8. **Exits** successfully, allowing the main app to start

## Environment Variables

The service expects these environment variables:

- `DATABASE_HOST` - PostgreSQL host (typically 'db' in Docker Compose)
- `DATABASE_USER` - PostgreSQL username
- `DATABASE_PASSWORD` - PostgreSQL password  
- `DATABASE_SCHEMA` - Database name to create/use
- `PYTHON_VERSION` - Python version to use (set automatically to 3.12)


**Migration Inspection Output:**
- Current database revision

