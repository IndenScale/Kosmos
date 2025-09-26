#!/usr/bin/env python
"""
Comprehensive script to fix PostgreSQL enum case sensitivity issues.
This script connects to the database and updates enums to support both uppercase and lowercase values.
"""

import os
import subprocess
from typing import List, Tuple

def get_current_enum_values() -> List[Tuple[str, List[str]]]:
    """Get all enum types and their values from the database"""
    
    # SQL query to get enum types and values
    sql = """
    SELECT t.typname AS enum_name, 
           array_agg(e.enumlabel ORDER BY e.enumsortorder) AS enum_values
    FROM pg_type t 
    JOIN pg_enum e ON t.oid = e.enumtypid
    GROUP BY t.typname;
    """
    
    cmd = [
        'docker', 'exec', 'kosmos-postgresql', 
        'psql', '-U', 'kosmos', '-d', 'kosmos', '-t', '-c', sql
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    enum_data = []
    lines = result.stdout.strip().split('\\n')
    for line in lines:
        if line.strip() and '|' in line:
            parts = line.strip().split('|')
            enum_name = parts[0].strip()
            # Parse the enum values array
            values_str = parts[1].strip()
            # Remove the curly braces and split by comma
            if values_str.startswith('{') and values_str.endswith('}'):
                values_str = values_str[1:-1]
                values = [v.strip().strip('"') for v in values_str.split(',')]
            else:
                values = [values_str.strip().strip('"')]
            enum_data.append((enum_name, values))
    
    return enum_data

def generate_enum_update_sql(enum_name: str, current_values: List[str]) -> str:
    """Generate SQL to update enum to include both uppercase and lowercase values"""
    
    # Create new enum values with both cases
    new_values = set()
    for v in current_values:
        new_values.add(v.lower())
        new_values.add(v.upper())
    
    # Generate SQL to recreate the enum type
    values_list = "', '".join(sorted(list(new_values)))
    
    sql = f"""
-- Update enum type {enum_name} to include both uppercase and lowercase values
DO $$
BEGIN
    -- Create new enum type with temporary name
    CREATE TYPE public.{enum_name}_new AS ENUM ('{values_list}');
    
    -- Update columns using the old enum to use the new enum temporarily
    -- We need to handle each table that uses this enum
    """
    
    # Add ALTER TABLE statements for each table that uses this enum
    # First, find which tables use this enum
    find_usage_sql = f"""
    SELECT table_name, column_name 
    FROM information_schema.columns 
    WHERE udt_name = '{enum_name}';
    """
    
    cmd = [
        'docker', 'exec', 'kosmos-postgresql', 
        'psql', '-U', 'kosmos', '-d', 'kosmos', '-t', '-c', find_usage_sql
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    for line in result.stdout.strip().split('\\n'):
        if line.strip() and '|' in line:
            parts = line.strip().split('|')
            table_name = parts[0].strip()
            column_name = parts[1].strip()
            
            sql += f"""
    -- Update column {table_name}.{column_name} to use new enum type
    ALTER TABLE {table_name} ALTER COLUMN {column_name} TYPE text USING {column_name}::text;
    ALTER TABLE {table_name} ALTER COLUMN {column_name} TYPE {enum_name}_new USING {column_name}::text::{enum_name}_new;
    """
    
    sql += f"""
    
    -- Drop old enum type
    DROP TYPE public.{enum_name};
    
    -- Rename new enum type to original name
    ALTER TYPE public.{enum_name}_new RENAME TO {enum_name};
    
END$$;
"""
    
    return sql

def export_and_fix_enum_schema():
    """Main function to export schema and fix enum case sensitivity"""
    
    print("Step 1: Getting current enum values from database...")
    enums = get_current_enum_values()
    
    print(f"Found {len(enums)} enum types in the database:")
    for enum_name, values in enums:
        print(f"  - {enum_name}: {values}")
    
    print("\\nStep 2: Generating SQL to update enums with both case values...")
    
    full_sql = []
    full_sql.append("-- Generated SQL to fix enum case sensitivity issues\\n")
    
    for enum_name, values in enums:
        sql = generate_enum_update_sql(enum_name, values)
        full_sql.append(sql)
    
    # Write the full SQL script
    script_content = "\\n".join(full_sql)
    
    script_path = "/tmp/fix_enum_case.sql"
    with open(script_path, 'w') as f:
        f.write(script_content)
    
    print(f"\\nStep 3: SQL script generated at {script_path}")
    
    # Execute the script against the database
    print("Step 4: Executing the enum case fix script...")
    cmd = ['docker', 'exec', '-i', 'kosmos-postgresql', 
           'psql', '-U', 'kosmos', '-d', 'kosmos', '-f', '/tmp/fix_enum_case.sql']
    
    # Copy the file to the container first
    cp_cmd = ['docker', 'cp', script_path, 'kosmos-postgresql:/tmp/fix_enum_case.sql']
    cp_result = subprocess.run(cp_cmd, capture_output=True, text=True)
    
    if cp_result.returncode != 0:
        print(f"Error copying script to container: {cp_result.stderr}")
        return False

    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode == 0:
        print("Enum case fix completed successfully!")
        print(result.stdout)
        return True
    else:
        print(f"Error executing enum fix script: {result.stderr}")
        return False

def verify_fix():
    """Verify that the enums now have both case values"""
    print("\\nStep 5: Verifying the fix...")
    
    sql = """
    SELECT t.typname AS enum_name, 
           array_agg(e.enumlabel ORDER BY e.enumsortorder) AS enum_values
    FROM pg_type t 
    JOIN pg_enum e ON t.oid = e.enumtypid
    GROUP BY t.typname;
    """
    
    cmd = [
        'docker', 'exec', 'kosmos-postgresql', 
        'psql', '-U', 'kosmos', '-d', 'kosmos', '-t', '-c', sql
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    print("Current enum values after fix:")
    lines = result.stdout.strip().split('\\n')
    for line in lines:
        if line.strip() and '|' in line:
            parts = line.strip().split('|')
            enum_name = parts[0].strip()
            values_str = parts[1].strip()
            # Parse values
            if values_str.startswith('{') and values_str.endswith('}'):
                values_str = values_str[1:-1]
                values = [v.strip().strip('"') for v in values_str.split(',')]
            else:
                values = [values_str.strip().strip('"')]
            print(f"  - {enum_name}: {values}")

if __name__ == "__main__":
    print("Starting enum case sensitivity fix...")
    success = export_and_fix_enum_schema()
    if success:
        verify_fix()
        print("\\nEnum case sensitivity fix completed!")
    else:
        print("\\nEnum case sensitivity fix failed!")
        exit(1)