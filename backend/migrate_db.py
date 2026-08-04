import os
import sys
from sqlalchemy import create_engine, MetaData
from sqlalchemy.orm import sessionmaker

def migrate_data():
    neon_url = "postgresql://neondb_owner:npg_ZzBiN3DU6dgc@ep-holy-lake-aiso6dd5-pooler.c-4.us-east-1.aws.neon.tech/neondb?sslmode=require"
    local_url = "postgresql://sisc_user:sisc_password@db:5432/sisc_jamundi"
    
    print("Connecting to Neon DB...")
    neon_engine = create_engine(neon_url)
    neon_metadata = MetaData()
    try:
        from geoalchemy2 import Geometry
    except ImportError:
        pass
    neon_metadata.reflect(bind=neon_engine)
    print(f"Neon tables found: {list(neon_metadata.tables.keys())}")
    
    print("Connecting to Local DB...")
    local_engine = create_engine(local_url)
    local_metadata = MetaData()
    # It assumes the tables are already created locally. If not, we create them from the reflected metadata.
    try:
        neon_metadata.create_all(bind=local_engine)
        print("Created tables locally if they didn't exist.")
    except Exception as e:
        print(f"Error creating tables: {e}")
        
    local_metadata.reflect(bind=local_engine)
    print(f"Local tables found: {list(local_metadata.tables.keys())}")

    # Disable foreign key checks for the session.
    # In postgres, either truncate cascade or defer constraints. But since db is probably empty or we truncate it:
    with local_engine.connect() as local_conn:
        try:
            local_conn.execute("SET session_replication_role = replica;")
        except Exception:
            pass

    # Copy data table by table
    for table_name in neon_metadata.tables:
        neon_table = neon_metadata.tables[table_name]
        print(f"Migrating table {table_name}...")
        
        with neon_engine.connect() as neon_conn:
            # Fetch all rows from neon
            result = neon_conn.execute(neon_table.select()).fetchall()
            
            if not result:
                print(f"Table {table_name} is empty.")
                continue
                
            print(f"Fetched {len(result)} rows for {table_name}.")
            
            with local_engine.connect() as local_conn:
                local_table = local_metadata.tables[table_name]
                
                # Delete existing data to avoid PK conflicts
                try:
                    local_conn.execute(local_table.delete())
                except Exception as e:
                    print(f"Could not delete local table data: {e}")
                
                # Insert chunks
                chunk_size = 1000
                for i in range(0, len(result), chunk_size):
                    chunk = result[i:i + chunk_size]
                    ins = local_table.insert().values(chunk)
                    local_conn.execute(ins)
                print(f"Inserted {len(result)} rows into local {table_name}.")

    # Re-enable checks
    with local_engine.connect() as local_conn:
        try:
            local_conn.execute("SET session_replication_role = DEFAULT;")
        except Exception:
            pass
            
    # Reset Sequences for serial columns
    print("Resetting sequences...")
    with local_engine.connect() as local_conn:
        for table_name in local_metadata.tables:
            # A simple query to fix sequences logic for PG
            query = f"""
            DO $$
            DECLARE
                seq_name text;
                max_id integer;
            BEGIN
                FOR seq_name IN
                    SELECT seq.relname
                    FROM pg_class seq
                    JOIN pg_depend dep ON seq.oid = dep.objid
                    JOIN pg_class tab ON dep.refobjid = tab.oid
                    JOIN pg_attribute att ON dep.refobjid = att.attrelid AND dep.refobjsubid = att.attnum
                    WHERE seq.relkind = 'S' AND tab.relname = '{table_name}'
                LOOP
                    EXECUTE 'SELECT COALESCE(MAX(id), 1) FROM ' || quote_ident('{table_name}') INTO max_id;
                    EXECUTE 'ALTER SEQUENCE ' || quote_ident(seq_name) || ' RESTART WITH ' || (max_id + 1);
                END LOOP;
            END $$;
            """
            try:
                local_conn.execute(query)
            except Exception as e:
                pass


    print("Migration complete!")

if __name__ == "__main__":
    migrate_data()
