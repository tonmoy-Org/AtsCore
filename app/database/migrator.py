import os
import io
import csv
import sqlite3
import time
import logging
from app.config import Config
from app.database.connection import get_pg_connection, get_pg_cursor
from app.database.schema import init_enterprise_schema, ensure_sheet_table

logger = logging.getLogger("atscore.migrator")


def run_migration_from_sqlite(sqlite_path=None, chunk_size=50000):
    """
    High-Speed Enterprise ETL Pipeline:
    Migrates 14M+ records from Fast_Excel_Sheet.db into PostgreSQL 16 using native COPY stream.
    """
    if sqlite_path is None:
        sqlite_path = Config.SQLITE_SOURCE_PATH

    if not os.path.exists(sqlite_path):
        raise FileNotFoundError(f"Source SQLite database not found at: {sqlite_path}")

    print(f"\n=======================================================")
    print(f"⚡ AtsCore Ultra-Fast PostgreSQL Migration Engine ⚡")
    print(f"=======================================================")
    print(f"Source: {sqlite_path}")
    print(f"Target: PostgreSQL @ {Config.PG_HOST}:{Config.PG_PORT}/{Config.PG_DATABASE}\n")

    t_start = time.perf_counter()

    # Step 1: Ensure enterprise schema
    init_enterprise_schema()

    sq_conn = sqlite3.connect(sqlite_path)
    sq_cur = sq_conn.cursor()

    # -------------------------------------------------------------------------
    # 1. sheets_meta
    # -------------------------------------------------------------------------
    print("▶ Migrating 'sheets_meta'...")
    sq_cur.execute(
        "SELECT sheet_id, name, row_count, sort_order, tab_color, col_styles_json, "
        "col_widths_json, freeze_rows, freeze_cols, merges_json FROM sheets_meta"
    )
    meta_rows = sq_cur.fetchall()
    with get_pg_cursor() as pg_cur:
        for r in meta_rows:
            pg_cur.execute(
                """
                INSERT INTO sheets_meta (
                    sheet_id, name, row_count, sort_order, tab_color,
                    col_styles_json, col_widths_json, freeze_rows, freeze_cols, merges_json
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (sheet_id) DO UPDATE SET
                    name = EXCLUDED.name,
                    row_count = EXCLUDED.row_count,
                    sort_order = EXCLUDED.sort_order,
                    tab_color = EXCLUDED.tab_color,
                    col_styles_json = EXCLUDED.col_styles_json,
                    col_widths_json = EXCLUDED.col_widths_json,
                    freeze_rows = EXCLUDED.freeze_rows,
                    freeze_cols = EXCLUDED.freeze_cols,
                    merges_json = EXCLUDED.merges_json;
                """,
                r
            )
        pg_cur.execute("SELECT setval('sheets_meta_sheet_id_seq', (SELECT COALESCE(MAX(sheet_id), 1) FROM sheets_meta))")
    print(f"✓ 'sheets_meta' migrated successfully ({len(meta_rows)} sheets).\n")

    # -------------------------------------------------------------------------
    # 2. live_inventory_ledger
    # -------------------------------------------------------------------------
    print("▶ Migrating 'live_inventory_ledger'...")
    try:
        sq_cur.execute(
            "SELECT sheet_id, sheet_name, operator, total_rows, colored_rows, available_rows FROM live_inventory_ledger"
        )
        ledger_rows = sq_cur.fetchall()
        if ledger_rows:
            with get_pg_cursor() as pg_cur:
                for r in ledger_rows:
                    pg_cur.execute(
                        """
                        INSERT INTO live_inventory_ledger (
                            sheet_id, sheet_name, operator, total_rows, colored_rows, available_rows
                        )
                        VALUES (%s, %s, %s, %s, %s, %s)
                        ON CONFLICT (sheet_id, operator) DO UPDATE SET
                            sheet_name = EXCLUDED.sheet_name,
                            total_rows = EXCLUDED.total_rows,
                            colored_rows = EXCLUDED.colored_rows,
                            available_rows = EXCLUDED.available_rows;
                        """,
                        r
                    )
            print(f"✓ 'live_inventory_ledger' migrated ({len(ledger_rows)} records).\n")
    except Exception as e:
        print(f"Notice (live_inventory_ledger): {e}")

    # -------------------------------------------------------------------------
    # 3. dashboard_cache
    # -------------------------------------------------------------------------
    print("▶ Migrating 'dashboard_cache'...")
    try:
        sq_cur.execute("SELECT cache_key, json_data, updated_at FROM dashboard_cache")
        dash_rows = sq_cur.fetchall()
        if dash_rows:
            with get_pg_cursor() as pg_cur:
                for r in dash_rows:
                    pg_cur.execute(
                        """
                        INSERT INTO dashboard_cache (cache_key, json_data, updated_at)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (cache_key) DO UPDATE SET
                            json_data = EXCLUDED.json_data,
                            updated_at = EXCLUDED.updated_at;
                        """,
                        r
                    )
            print(f"✓ 'dashboard_cache' migrated ({len(dash_rows)} records).\n")
    except Exception as e:
        print(f"Notice (dashboard_cache): {e}")

    # -------------------------------------------------------------------------
    # 4. Dynamic sheet_X tables (5.36M+ rows)
    # -------------------------------------------------------------------------
    # The active sheet tables correspond exactly to the sheets defined in sheets_meta
    meta_sheet_tables = [f"sheet_{r[0]}" for r in meta_rows]
    
    # Check for any auxiliary sheet backup tables (strictly excluding sheets_meta and sheet_styles)
    sq_cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    all_sq_tables = {row[0] for row in sq_cur.fetchall()}
    auxiliary_tables = [
        t for t in all_sq_tables 
        if t.startswith("sheet_") and t not in ("sheets_meta", "sheet_styles") and t not in meta_sheet_tables
    ]
    all_sheet_tables = meta_sheet_tables + auxiliary_tables

    print(f"▶ Found {len(all_sheet_tables)} sheet tables to migrate ({len(meta_sheet_tables)} active + {len(auxiliary_tables)} auxiliary).")

    cols_az = Config.COLS_AZ
    cols_quoted = f'row_idx, {", ".join(f"\"{c}\"" for c in cols_az)}'
    cols_def = ", ".join(f'"{c}" TEXT DEFAULT \'\'' for c in cols_az)
    total_migrated_sheet_rows = 0

    with get_pg_connection() as pg_conn:
        with pg_conn.cursor() as pg_cur:
            for i, t_name in enumerate(all_sheet_tables, 1):
                # Dynamically create table if not exists
                pg_cur.execute(f"""
                    CREATE TABLE IF NOT EXISTS "{t_name}" (
                        row_idx INTEGER PRIMARY KEY,
                        {cols_def}
                    );
                    CREATE INDEX IF NOT EXISTS "idx_{t_name}_a" ON "{t_name}" ("A");
                """)
                pg_cur.execute(f'TRUNCATE TABLE "{t_name}"')

                sq_cur.execute(f"SELECT count(*) FROM {t_name}")
                t_total = sq_cur.fetchone()[0]

                sq_cur.execute(f"SELECT row_idx, {', '.join(cols_az)} FROM {t_name}")
                t_migrated = 0

                while True:
                    rows = sq_cur.fetchmany(chunk_size)
                    if not rows:
                        break

                    buf = io.StringIO()
                    writer = csv.writer(buf, delimiter='\t', lineterminator='\n', quoting=csv.QUOTE_MINIMAL)
                    writer.writerows(rows)
                    buf.seek(0)

                    pg_cur.copy_expert(
                        f'COPY "{t_name}" ({cols_quoted}) FROM STDIN WITH (FORMAT CSV, DELIMITER E\'\\t\')',
                        buf
                    )
                    t_migrated += len(rows)

                pg_conn.commit()
                total_migrated_sheet_rows += t_migrated
                print(f"  [{i:02d}/{len(all_sheet_tables)}] Table '{t_name}': {t_migrated:,} rows copied.")

    print(f"\n✓ All {len(all_sheet_tables)} sheets migrated! Total rows: {total_migrated_sheet_rows:,}\n")

    # -------------------------------------------------------------------------
    # 5. sheet_styles (8.9M+ rows)
    # -------------------------------------------------------------------------
    print("▶ Migrating 'sheet_styles' (8.9M+ formatting records)...")
    sq_cur.execute("SELECT count(*) FROM sheet_styles")
    total_styles = sq_cur.fetchone()[0]
    print(f"  Total styles in SQLite: {total_styles:,}")

    with get_pg_connection() as pg_conn:
        with pg_conn.cursor() as pg_cur:
            # Drop primary key and index temporarily for max ingestion speed
            print("  Optimizing PostgreSQL: Dropping constraints temporarily...")
            pg_cur.execute("ALTER TABLE sheet_styles DROP CONSTRAINT IF EXISTS sheet_styles_pkey CASCADE")
            pg_cur.execute("DROP INDEX IF EXISTS idx_sheet_styles_sheet_row")
            pg_cur.execute("TRUNCATE TABLE sheet_styles")
            pg_conn.commit()

            print("  Streaming styles via high-speed COPY buffer...")
            sq_cur.execute("SELECT sheet_id, row_idx, col_key, style_json FROM sheet_styles")
            styles_copied = 0
            styles_chunk = 100000
            t_styles_start = time.perf_counter()

            while True:
                s_batch = sq_cur.fetchmany(styles_chunk)
                if not s_batch:
                    break

                buf = io.StringIO()
                writer = csv.writer(buf, delimiter='\t', quoting=csv.QUOTE_MINIMAL, lineterminator='\n')
                writer.writerows(s_batch)
                buf.seek(0)

                pg_cur.copy_expert(
                    "COPY sheet_styles (sheet_id, row_idx, col_key, style_json) FROM STDIN WITH (FORMAT CSV, DELIMITER E'\\t', QUOTE '\"')",
                    buf
                )
                styles_copied += len(s_batch)
                pct = (styles_copied / max(total_styles, 1)) * 100.0
                rate = int(styles_copied / max(time.perf_counter() - t_styles_start, 0.001))
                print(f"  Styles: {styles_copied:,} / {total_styles:,} ({pct:.1f}%) — {rate:,} rows/sec")

            pg_conn.commit()

            # Rebuild primary key and index
            print("  Rebuilding Primary Key (sheet_id, row_idx, col_key)...")
            pg_cur.execute("ALTER TABLE sheet_styles ADD PRIMARY KEY (sheet_id, row_idx, col_key)")
            print("  Rebuilding Index idx_sheet_styles_sheet_row...")
            pg_cur.execute("CREATE INDEX IF NOT EXISTS idx_sheet_styles_sheet_row ON sheet_styles (sheet_id, row_idx)")
            print("  Analyzing table...")
            pg_cur.execute("ANALYZE sheet_styles")
            pg_conn.commit()

    sq_conn.close()

    total_time = round(time.perf_counter() - t_start, 2)
    grand_total_records = len(meta_rows) + total_migrated_sheet_rows + styles_copied

    print(f"\n=======================================================")
    print(f"🎉 MIGRATION COMPLETED SUCCESSFULLY IN {total_time} SECONDS! 🎉")
    print(f"=======================================================")
    print(f"• Sheets Meta:         {len(meta_rows):,} sheets")
    print(f"• Dynamic Sheets:      {len(all_sheet_tables):,} tables ({total_migrated_sheet_rows:,} rows)")
    print(f"• Cell Formatting:     {styles_copied:,} style records")
    print(f"• Total Data Migrated: {grand_total_records:,} records")
    print(f"• Ingestion Speed:     {int(grand_total_records / max(total_time, 0.1)):,} records/sec")
    print(f"=======================================================\n")

    # Invalidate & rebuild DragonflyDB cache
    try:
        from app.services.sheet_service import SheetService
        from app.services.dashboard_service import DashboardService
        SheetService.invalidate_cache()
        DashboardService.get_dashboard_stats(force_rebuild=True)
        print("✓ DragonflyDB L1 Cache warmed up successfully.")
    except Exception as e:
        print(f"Cache warm notice: {e}")

    return {
        "status": "success",
        "sheets_count": len(meta_rows),
        "sheet_tables": len(all_sheet_tables),
        "sheet_rows": total_migrated_sheet_rows,
        "styles_count": styles_copied,
        "total_records": grand_total_records,
        "elapsed_seconds": total_time,
    }
