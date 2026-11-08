#!/usr/bin/env python3
"""
AtsCore Management CLI and Entry Point
======================================
Usage:
  python manage.py runserver              # Starts Flask server locally
  python manage.py init-db                # Initializes PostgreSQL enterprise schema
  python manage.py migrate-sqlite         # Migrates Fast_Excel_Sheet.db into PostgreSQL
  python manage.py test-connections       # Tests PostgreSQL & DragonflyDB connectivity
"""

import sys
import logging
from app import create_app
from app.config import Config
from app.database import init_enterprise_schema, check_pg_health
from app.database.migrator import run_migration_from_sqlite
from app.cache.dragonfly import get_dragonfly_telemetry, verify_dragonfly_pipeline

logger = logging.getLogger("atscore.cli")

app = create_app()


def print_help():
    print("""
AtsCore Enterprise Backend CLI
------------------------------
Available commands:
  runserver         : Run the Flask server locally
  init-db           : Initialize PostgreSQL enterprise schema & tables
  migrate-sqlite    : Run ETL migration from Fast_Excel_Sheet.db -> PostgreSQL
  test-connections  : Check PostgreSQL & DragonflyDB connectivity & benchmark
""")


def main():
    if len(sys.argv) < 2:
        cmd = "runserver"
    else:
        cmd = sys.argv[1].lower()

    if cmd == "runserver":
        print(f"Starting AtsCore Backend on {Config.HOST}:{Config.PORT}...")
        app.run(host=Config.HOST, port=Config.PORT, debug=Config.DEBUG)

    elif cmd == "init-db":
        print("Initializing PostgreSQL Enterprise Schema...")
        init_enterprise_schema()
        print("Schema initialization completed successfully!")

    elif cmd == "migrate-sqlite":
        source = sys.argv[2] if len(sys.argv) > 2 else None
        if not source:
            print("Error: Source SQLite database path required. Usage: python manage.py migrate-sqlite <path_to_sqlite.db>")
            return
        print(f"Starting SQLite to PostgreSQL migration from: {source}")
        res = run_migration_from_sqlite(source)
        print("Migration Result:", res)

    elif cmd == "test-connections":
        print("Testing PostgreSQL Connection...")
        pg = check_pg_health()
        print("PostgreSQL Status:", pg)

        print("\nTesting DragonflyDB Connection...")
        df = get_dragonfly_telemetry()
        print("DragonflyDB Status:", df)

        if df.get("online"):
            print("\nRunning Pipeline Benchmark (100 ops)...")
            bench = verify_dragonfly_pipeline(100)
            print("Benchmark Result:", bench)

    else:
        print_help()


if __name__ == "__main__":
    main()

