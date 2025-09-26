#!/usr/bin/env python
"""
Comprehensive script to fix database schema issues in PostgreSQL database.
This script connects to the database and ensures all required columns and types exist.
"""
import sys
from sqlalchemy import create_engine, text, inspect
from backend.app.core.config import settings

def check_and_fix_assets_table():
    """Check and fix the assets table schema if needed."""
    
    # Use the computed database URL
    db_url = settings.computed_DATABASE_URL
    print(f"Connecting to database: {db_url}")
    engine = create_engine(db_url)
    
    with engine.connect() as conn:
        # Check if we're using PostgreSQL
        if engine.dialect.name != 'postgresql':
            print(f"This script is designed for PostgreSQL databases, but current dialect is {engine.dialect.name}")
            # Continue anyway if we're specifically targeting PostgreSQL
            if 'postgresql' in db_url:
                print("Warning: Database URL suggests PostgreSQL, but dialect detected as different type")
            else:
                print("Exiting as this script is meant for PostgreSQL databases")
                return False
        
        # Get current columns in assets table
        inspector = inspect(engine)
        columns = inspector.get_columns('assets')
        column_names = [col['name'] for col in columns]
        
        print(f"Current columns in assets table: {column_names}")
        
        # Check for missing columns based on the model
        required_columns = ['id', 'asset_hash', 'asset_type', 'file_type', 'size', 'storage_path', 'reference_count', 'analysis_status', 'created_at', 'last_accessed_at']
        missing_columns = [col for col in required_columns if col not in column_names]
        
        if not missing_columns:
            print("All required columns exist in the assets table.")
            return True
        
        print(f"Missing columns in assets table: {missing_columns}")
        
        # Create enum types if they don't exist
        create_asset_types_enum = text("""
            DO $$ 
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'asset_types_enum') THEN
                    CREATE TYPE asset_types_enum AS ENUM ('figure', 'table', 'audio', 'video');
                END IF;
            END$$;
        """)
        
        create_asset_analysis_status_enum = text("""
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'asset_analysis_status_enum') THEN
                    CREATE TYPE asset_analysis_status_enum AS ENUM ('not_analyzed', 'pending', 'in_progress', 'completed', 'failed');
                END IF;
            END$$;
        """)
        
        conn.execute(create_asset_types_enum)
        conn.execute(create_asset_analysis_status_enum)
        conn.commit()
        
        # Add missing columns
        for col in missing_columns:
            if col == 'asset_type':
                alter_query = text("ALTER TABLE assets ADD COLUMN asset_type asset_types_enum NOT NULL DEFAULT 'figure';")
            elif col == 'analysis_status':
                alter_query = text("ALTER TABLE assets ADD COLUMN analysis_status asset_analysis_status_enum NOT NULL DEFAULT 'not_analyzed';")
            elif col == 'asset_hash':
                alter_query = text("ALTER TABLE assets ADD COLUMN asset_hash VARCHAR UNIQUE;")
            elif col == 'file_type':
                alter_query = text("ALTER TABLE assets ADD COLUMN file_type VARCHAR NOT NULL DEFAULT 'unknown';")
            elif col == 'size':
                alter_query = text("ALTER TABLE assets ADD COLUMN size INTEGER NOT NULL DEFAULT 0;")
            elif col == 'storage_path':
                alter_query = text("ALTER TABLE assets ADD COLUMN storage_path VARCHAR NOT NULL DEFAULT '';")
            elif col == 'reference_count':
                alter_query = text("ALTER TABLE assets ADD COLUMN reference_count INTEGER DEFAULT 1 NOT NULL;")
            elif col == 'created_at':
                alter_query = text("ALTER TABLE assets ADD COLUMN created_at TIMESTAMP NOT NULL DEFAULT NOW();")
            elif col == 'last_accessed_at':
                alter_query = text("ALTER TABLE assets ADD COLUMN last_accessed_at TIMESTAMP NOT NULL DEFAULT NOW();")
            elif col == 'id':
                print("ERROR: Cannot safely add id column to existing table")
                continue
            else:
                print(f"Unknown column {col}, skipping...")
                continue
            
            try:
                conn.execute(alter_query)
                conn.commit()
                print(f"Successfully added column '{col}' to assets table.")
            except Exception as e:
                print(f"Error adding column '{col}': {e}")
                conn.rollback()
        
        print("Assets table fix completed.")
        return True

if __name__ == "__main__":
    try:
        success = check_and_fix_assets_table()
        if success:
            print("Database schema fix completed successfully.")
            sys.exit(0)
        else:
            print("Database schema fix failed.")
            sys.exit(1)
    except Exception as e:
        print(f"An error occurred: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)