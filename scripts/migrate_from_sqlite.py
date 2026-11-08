#!/usr/bin/env python3
"""
ETL Data Migrator Script
Direct runner: python scripts/migrate_from_sqlite.py [sqlite_file_path]
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database.migrator import run_migration_from_sqlite
from app.config import Config

if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else Config.SQLITE_SOURCE_PATH
    print(f"=== Starting AtsCore SQLite to PostgreSQL Migration ===")
    print(f"Source Database: {src}")
    print(f"Target Database: {Config.PG_DATABASE} @ {Config.PG_HOST}:{Config.PG_PORT}")
    try:
        res = run_migration_from_sqlite(src)
        print("\n Migration Complete!")
        print(f"Sheets migrated: {res.get('sheets_count')}")
        print(f"Dynamic tables migrated: {res.get('tables_migrated')}")
        print(f"Time taken: {res.get('elapsed_seconds')} seconds")
    except Exception as e:
        print(f"\n❌ Migration Failed: {e}")
        sys.exit(1)

