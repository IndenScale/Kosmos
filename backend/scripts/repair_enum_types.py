"""
Database enum type repair script
This script fixes the enum type issue by recreating it properly
"""
import sys
import os

# Add the backend directory to the path so we can import the models
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from sqlalchemy import create_engine, text
from app.core.config import settings
from app.models.asset import AssetAnalysisStatus, AssetType
from app.models.base import Base


def recreate_enum_types():
    """Drop and recreate enum types to ensure they match model definitions."""
    engine = create_engine(settings.DATABASE_URL)
    
    with engine.connect() as conn:
        # Begin a transaction
        trans = conn.begin()
        try:
            # Get all tables that use the enum type
            result = conn.execute(text("""
                SELECT table_name, column_name
                FROM information_schema.columns
                WHERE data_type = 'USER-DEFINED' AND udt_name = 'asset_analysis_status_enum'
            """))
            
            tables_using_enum = [(row[0], row[1]) for row in result]
            
            # Drop existing enum type if it exists
            conn.execute(text("DROP TYPE IF EXISTS asset_analysis_status_enum CASCADE;"))
            conn.execute(text("DROP TYPE IF EXISTS asset_types_enum CASCADE;"))
            
            # Create the enum types based on our Python definitions
            analysis_status_values = [status.value for status in AssetAnalysisStatus]
            analysis_status_enum_def = "'" + "', '".join(analysis_status_values) + "'"
            
            asset_type_values = [asset_type.value for asset_type in AssetType]
            asset_type_enum_def = "'" + "', '".join(asset_type_values) + "'"
            
            # Create asset_analysis_status_enum
            conn.execute(
                text(f"CREATE TYPE asset_analysis_status_enum AS ENUM ({analysis_status_enum_def});")
            )
            
            # Create asset_types_enum
            conn.execute(
                text(f"CREATE TYPE asset_types_enum AS ENUM ({asset_type_enum_def});")
            )
            
            # Commit the transaction
            trans.commit()
            print("Enum types have been successfully recreated to match model definitions.")
            
        except Exception as e:
            print(f"Error recreating enum types: {e}")
            trans.rollback()
            raise


def main():
    """Main function to run the enum type recreation."""
    print("Recreating PostgreSQL enum types to match model definitions...")
    recreate_enum_types()
    print("Enum types are now properly aligned with model definitions.")


if __name__ == "__main__":
    main()