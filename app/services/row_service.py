import json
import logging
from psycopg2.extras import execute_values
from app.config import Config
from app.database.connection import get_pg_cursor, get_pg_connection

logger = logging.getLogger("atscore.row_service")


class RowService:
    @staticmethod
    def get_rows(sheet_id: int, offset: int = 0, limit: int = 1000, search: str = ""):
        """
        Retrieves paginated rows and their cell formatting styles.
        """
        table_name = f"sheet_{sheet_id}"
        cols_str = ", ".join(f'"{c}"' for c in Config.COLS_AZ)

        with get_pg_cursor(dict_cursor=True) as cur:
            if search:
                # Search across primary columns A, B, C, D
                cur.execute(
                    f"""
                    SELECT row_idx, {cols_str}
                    FROM "{table_name}"
                    WHERE "A" ILIKE %s OR "B" ILIKE %s OR "C" ILIKE %s OR "D" ILIKE %s
                    ORDER BY row_idx ASC
                    LIMIT %s OFFSET %s
                    """,
                    (f"%{search}%", f"%{search}%", f"%{search}%", f"%{search}%", limit, offset)
                )
            else:
                cur.execute(
                    f"""
                    SELECT row_idx, {cols_str}
                    FROM "{table_name}"
                    ORDER BY row_idx ASC
                    LIMIT %s OFFSET %s
                    """,
                    (limit, offset)
                )
            raw_rows = cur.fetchall()

            if not raw_rows:
                return {"rows": [], "styles": {}, "total": 0}

            min_row = raw_rows[0]["row_idx"]
            max_row = raw_rows[-1]["row_idx"]

            # Fetch styles for these rows
            cur.execute(
                """
                SELECT row_idx, col_key, style_json
                FROM sheet_styles
                WHERE sheet_id = %s AND row_idx >= %s AND row_idx <= %s
                """,
                (sheet_id, min_row, max_row)
            )
            styles_map = {}
            for s in cur.fetchall():
                r_i = s["row_idx"]
                c_k = s["col_key"]
                if r_i not in styles_map:
                    styles_map[r_i] = {}
                try:
                    styles_map[r_i][c_k] = json.loads(s["style_json"])
                except Exception:
                    styles_map[r_i][c_k] = s["style_json"]

            cur.execute(f'SELECT COUNT(*) FROM "{table_name}"')
            total_count = cur.fetchone()["count"]

            return {
                "rows": raw_rows,
                "styles": styles_map,
                "total": total_count,
                "offset": offset,
                "limit": limit
            }

    @staticmethod
    def update_cell(sheet_id: int, row_idx: int, col: str, val: str):
        col_clean = col.upper().strip()
        if col_clean not in Config.COLS_AZ:
            raise ValueError(f"Invalid column: {col}")

        table_name = f"sheet_{sheet_id}"
        with get_pg_cursor() as cur:
            cur.execute(
                f"""
                INSERT INTO "{table_name}" (row_idx, "{col_clean}")
                VALUES (%s, %s)
                ON CONFLICT (row_idx) DO UPDATE SET "{col_clean}" = EXCLUDED."{col_clean}"
                """,
                (row_idx, val)
            )
        return True

    @staticmethod
    def batch_update_cells(sheet_id: int, updates: list):
        """
        Updates a batch of cells: [{"row": 1, "col": "A", "val": "..."}, ...]
        """
        if not updates:
            return 0

        table_name = f"sheet_{sheet_id}"
        with get_pg_cursor() as cur:
            for item in updates:
                r_idx = item.get("row") or item.get("row_idx")
                c_key = (item.get("col") or item.get("col_key") or "A").upper().strip()
                val = str(item.get("val") or item.get("value") or "")
                if c_key in Config.COLS_AZ and r_idx:
                    cur.execute(
                        f"""
                        INSERT INTO "{table_name}" (row_idx, "{c_key}")
                        VALUES (%s, %s)
                        ON CONFLICT (row_idx) DO UPDATE SET "{c_key}" = EXCLUDED."{c_key}"
                        """,
                        (r_idx, val)
                    )
        return len(updates)

    @staticmethod
    def update_styles(sheet_id: int, style_entries: list):
        """
        Upserts style entries: [{"row": 1, "col": "A", "style": {...}}, ...]
        """
        if not style_entries:
            return 0

        tuples = []
        for it in style_entries:
            r = it.get("row") or it.get("row_idx")
            c = (it.get("col") or it.get("col_key") or "A").upper().strip()
            st = it.get("style")
            st_str = st if isinstance(st, str) else json.dumps(st or {})
            if r and c:
                tuples.append((sheet_id, r, c, st_str))

        if not tuples:
            return 0

        with get_pg_connection() as conn:
            with conn.cursor() as cur:
                execute_values(
                    cur,
                    """
                    INSERT INTO sheet_styles (sheet_id, row_idx, col_key, style_json)
                    VALUES %s
                    ON CONFLICT (sheet_id, row_idx, col_key) DO UPDATE SET
                        style_json = EXCLUDED.style_json
                    """,
                    tuples,
                    page_size=2000
                )
            conn.commit()
        return len(tuples)

    @staticmethod
    def clear_styles(sheet_id: int, row_start: int = None, row_end: int = None):
        with get_pg_cursor() as cur:
            if row_start is not None and row_end is not None:
                cur.execute(
                    "DELETE FROM sheet_styles WHERE sheet_id = %s AND row_idx >= %s AND row_idx <= %s",
                    (sheet_id, row_start, row_end)
                )
            else:
                cur.execute("DELETE FROM sheet_styles WHERE sheet_id = %s", (sheet_id,))
        return True

    @staticmethod
    def insert_row(sheet_id: int, target_row_idx: int):
        table_name = f"sheet_{sheet_id}"
        with get_pg_cursor() as cur:
            # Shift existing rows >= target_row_idx up by 1
            cur.execute(
                f"""
                UPDATE "{table_name}"
                SET row_idx = row_idx + 1
                WHERE row_idx >= %s
                """,
                (target_row_idx,)
            )
            # Insert empty row
            cur.execute(f'INSERT INTO "{table_name}" (row_idx) VALUES (%s)', (target_row_idx,))
            # Update row count in meta
            cur.execute("UPDATE sheets_meta SET row_count = row_count + 1 WHERE sheet_id = %s", (sheet_id,))
        return True

    @staticmethod
    def delete_rows(sheet_id: int, row_indices: list):
        if not row_indices:
            return 0

        table_name = f"sheet_{sheet_id}"
        with get_pg_cursor() as cur:
            cur.execute(
                f'DELETE FROM "{table_name}" WHERE row_idx = ANY(%s)',
                (row_indices,)
            )
            cur.execute(
                "DELETE FROM sheet_styles WHERE sheet_id = %s AND row_idx = ANY(%s)",
                (sheet_id, row_indices)
            )
            cur.execute(
                "UPDATE sheets_meta SET row_count = GREATEST(0, row_count - %s) WHERE sheet_id = %s",
                (len(row_indices), sheet_id)
            )
        return len(row_indices)

    @staticmethod
    def sort_sheet(sheet_id: int, col_key: str, ascending: bool = True):
        col_clean = col_key.upper().strip()
        if col_clean not in Config.COLS_AZ:
            raise ValueError(f"Invalid column for sorting: {col_key}")

        direction = "ASC" if ascending else "DESC"
        table_name = f"sheet_{sheet_id}"
        cols_str = ", ".join(f'"{c}"' for c in Config.COLS_AZ)

        with get_pg_cursor() as cur:
            cur.execute(
                f"""
                CREATE TEMP TABLE temp_sorted AS
                SELECT ROW_NUMBER() OVER (ORDER BY "{col_clean}" {direction} NULLS LAST) AS new_idx, {cols_str}
                FROM "{table_name}"
                WHERE row_idx > 1; -- preserve header row 1

                DELETE FROM "{table_name}" WHERE row_idx > 1;

                INSERT INTO "{table_name}" (row_idx, {cols_str})
                SELECT new_idx + 1, {cols_str} FROM temp_sorted;

                DROP TABLE temp_sorted;
                """
            )
        return True

