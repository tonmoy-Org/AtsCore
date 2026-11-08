import logging
from app.config import Config
from app.database.connection import get_pg_cursor

logger = logging.getLogger("atscore.schema")


def ensure_sheet_table(sheet_id: int):
    """
    Ensures that dynamic table sheet_{sheet_id} exists with columns row_idx, A..Z.
    """
    cols_def = ", ".join(f'"{c}" TEXT DEFAULT \'\'' for c in Config.COLS_AZ)
    table_name = f"sheet_{sheet_id}"
    sql = f"""
    CREATE TABLE IF NOT EXISTS "{table_name}" (
        row_idx INTEGER PRIMARY KEY,
        {cols_def}
    );
    CREATE INDEX IF NOT EXISTS "idx_{table_name}_a" ON "{table_name}" ("A");
    """
    with get_pg_cursor() as cur:
        cur.execute(sql)


def init_enterprise_schema():
    """
    Initializes PostgreSQL tables, indexes, and constraints for AtsCore.
    """
    logger.info("Initializing AtsCore PostgreSQL Enterprise Schema...")

    ddl_statements = [
        # 1. sheets_meta
        """
        CREATE TABLE IF NOT EXISTS sheets_meta (
            sheet_id SERIAL PRIMARY KEY,
            name VARCHAR(255) UNIQUE NOT NULL,
            row_count INTEGER DEFAULT 0,
            sort_order INTEGER DEFAULT 0,
            tab_color VARCHAR(64) DEFAULT '',
            col_styles_json TEXT DEFAULT '{}',
            col_widths_json TEXT DEFAULT '{}',
            freeze_rows INTEGER DEFAULT 0,
            freeze_cols INTEGER DEFAULT 0,
            merges_json TEXT DEFAULT '[]',
            created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'Asia/Dhaka'),
            updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'Asia/Dhaka')
        );
        """,
        # 2. sheet_styles
        """
        CREATE TABLE IF NOT EXISTS sheet_styles (
            sheet_id INTEGER NOT NULL,
            row_idx INTEGER NOT NULL,
            col_key VARCHAR(8) NOT NULL,
            style_json TEXT NOT NULL,
            PRIMARY KEY (sheet_id, row_idx, col_key)
        );
        CREATE INDEX IF NOT EXISTS idx_sheet_styles_sheet_row 
            ON sheet_styles (sheet_id, row_idx);
        """,
        # 3. live_inventory_ledger
        """
        CREATE TABLE IF NOT EXISTS live_inventory_ledger (
            sheet_id INTEGER NOT NULL,
            sheet_name VARCHAR(255) NOT NULL,
            operator VARCHAR(100) NOT NULL,
            total_rows INTEGER NOT NULL DEFAULT 0,
            colored_rows INTEGER NOT NULL DEFAULT 0,
            available_rows INTEGER NOT NULL DEFAULT 0,
            updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'Asia/Dhaka'),
            PRIMARY KEY (sheet_id, operator)
        );
        """,
        # 4. dashboard_cache
        """
        CREATE TABLE IF NOT EXISTS dashboard_cache (
            cache_key VARCHAR(128) PRIMARY KEY,
            json_data TEXT NOT NULL,
            updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'Asia/Dhaka')
        );
        """,
        # 5. telecom_bot_lease_log
        """
        CREATE TABLE IF NOT EXISTS telecom_bot_lease_log (
            id BIGSERIAL PRIMARY KEY,
            bot_id VARCHAR(128) NOT NULL,
            sheet_id INTEGER NOT NULL,
            sheet_name VARCHAR(255) NOT NULL,
            row_idx INTEGER NOT NULL,
            phone_number VARCHAR(64),
            carrier VARCHAR(64),
            circle VARCHAR(128),
            status VARCHAR(32) DEFAULT 'LEASED',
            leased_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (NOW() AT TIME ZONE 'Asia/Dhaka'),
            completed_at TIMESTAMP WITHOUT TIME ZONE
        );
        CREATE INDEX IF NOT EXISTS idx_bot_lease_phone ON telecom_bot_lease_log (phone_number);
        CREATE INDEX IF NOT EXISTS idx_bot_lease_status ON telecom_bot_lease_log (status);
        """
    ]

    with get_pg_cursor() as cur:
        for stmt in ddl_statements:
            cur.execute(stmt)

        # Ensure Sheet1 exists if sheets_meta is completely empty
        cur.execute("SELECT COUNT(*) FROM sheets_meta")
        count = cur.fetchone()[0]
        if count == 0:
            cur.execute(
                "INSERT INTO sheets_meta (sheet_id, name, row_count, sort_order) VALUES (1, 'Sheet1', 0, 1)"
            )
            ensure_sheet_table(1)

    logger.info("AtsCore PostgreSQL Enterprise Schema initialized successfully.")

