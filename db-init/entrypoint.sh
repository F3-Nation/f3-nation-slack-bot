#!/bin/bash

set -e

echo "🚀 Starting F3 Database Initialization..."

# Function to wait for database to be ready
wait_for_db() {
    echo "📡 Waiting for database to be ready..."
    
    # Default database connection parameters
    DB_HOST=${DATABASE_HOST:-localhost}
    DB_USER=${DATABASE_USER:-postgres}
    DB_PASS=${DATABASE_PASSWORD:-postgres}
    DB_NAME=${DATABASE_SCHEMA:-f3}
    
    # Wait for PostgreSQL to be ready
    until PGPASSWORD=$DB_PASS psql -h "$DB_HOST" -U "$DB_USER" -d postgres -c '\q' 2>/dev/null; do
        echo "🔄 Database is unavailable - sleeping..."
        sleep 5
    done
    
    echo "✅ Database is ready!"
}

# Function to create database if it doesn't exist
create_database() {
    echo "🔧 Checking if database '$DATABASE_SCHEMA' exists..."
    
    DB_EXISTS=$(PGPASSWORD=$DATABASE_PASSWORD psql -h "$DATABASE_HOST" -U "$DATABASE_USER" -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='$DATABASE_SCHEMA'" 2>/dev/null || echo "")
    
    if [ -z "$DB_EXISTS" ]; then
        echo "🏗️ Creating database '$DATABASE_SCHEMA'..."
        PGPASSWORD=$DATABASE_PASSWORD createdb -h "$DATABASE_HOST" -U "$DATABASE_USER" "$DATABASE_SCHEMA"
        echo "✅ Database '$DATABASE_SCHEMA' created!"
    else
        echo "✅ Database '$DATABASE_SCHEMA' already exists!"
    fi
}

# Function to run migrations
run_migrations() {
    echo "🗄️ Running Alembic migrations..."
    
    # Setup environment
    poetry env use $PYTHON_VERSION
    poetry install
    poetry run alembic upgrade head
    
    echo "✅ Database schema created successfully!"
}

# Function to show migration info without running them (for debugging/inspection)
show_migration_info() {
    echo "🔍 ALEMBIC MIGRATION INSPECTION (NO CHANGES APPLIED):"
    echo "======================================="
    
    # Setup environment
    poetry env use $PYTHON_VERSION
    poetry install
    
    # Show current database revision
    echo "🔍 Current database revision:"
    CURRENT_REV=$(poetry run alembic current 2>/dev/null || echo "No revision found")
    echo "   $CURRENT_REV"
    
    # Show migration history
    echo ""
    echo "📚 All available migrations:"
    poetry run alembic history --verbose 2>/dev/null || echo "   No migration history available"
    
}

# Main execution
main() {
    # Install postgresql-client for database operations
    apt-get update && apt-get install -y postgresql-client && rm -rf /var/lib/apt/lists/*
    
    wait_for_db
    create_database
    run_migrations
    show_migration_info

    # Show F3-Data-Models version info
    echo ""
    echo "======================================="
    echo "🏗️  F3-DATA-MODELS VERSION INFO:"
    echo "======================================="
    echo "🔑 Git Hash: $(cd /f3-data-models && git rev-parse HEAD 2>/dev/null || echo 'Unknown')"
    echo "📝 Latest Commit: $(cd /f3-data-models && git log --oneline -n 1 2>/dev/null || echo 'Unknown')"
    echo "📅 Commit Date: $(cd /f3-data-models && git log -1 --format=%cd --date=iso 2>/dev/null || echo 'Unknown')"
    echo "👤 Author: $(cd /f3-data-models && git log -1 --format='%an <%ae>' 2>/dev/null || echo 'Unknown')"
    echo "======================================="
    echo ""

    echo "🎉 F3 Database initialization completed successfully!"
    echo "📊 Database is ready for the F3 Nation Slack Bot!"
}

# Run main function
main "$@" 
