import json
import logging
from app.config import Config
from app.database.connection import get_pg_cursor
from app.database.schema import ensure_sheet_table
from app.cache.dragonfly import cache_get_json, cache_set_json, cache_invalidate_prefix

logger = logging.getLogger("atscore.sheet_service")

CACHE_KEY_SHEETS = "ats:ms:sheets_meta_list"


class SheetService:
    @staticmethod
    def get_all_sheets():
        """Returns list of all sheets metadata, utilizing DragonflyDB L1 cache."""
        cached = cache_get_json(CACHE_KEY_SHEETS)
        if cached is not None:
            return cached

        with get_pg_cursor(dict_cursor=True) as cur:
            cur.execute(
                """
                SELECT sheet_id, name, row_count, sort_order, tab_color,
                       col_styles_json, col_widths_json, freeze_rows, freeze_cols, merges_json
                FROM sheets_meta
                ORDER BY sort_order ASC, sheet_id ASC
                """
            )
            sheets = []
            for r in cur.fetchall():
                sheets.append({
                    "sheet_id": r["sheet_id"],
                    "name": r["name"],
                    "row_count": r["row_count"] or 0,
                    "sort_order": r["sort_order"] or 0,
                    "tab_color": r["tab_color"] or "",
                    "col_styles": json.loads(r["col_styles_json"]) if r["col_styles_json"] else {},
                    "col_widths": json.loads(r["col_widths_json"]) if r["col_widths_json"] else {},
                    "freeze_rows": r["freeze_rows"] or 0,
                    "freeze_cols": r["freeze_cols"] or 0,
                    "merges": json.loads(r["merges_json"]) if r["merges_json"] else [],
                })

            cache_set_json(CACHE_KEY_SHEETS, sheets, ttl=1800)
            return sheets

    @staticmethod
    def invalidate_cache():
        cache_invalidate_prefix("ats:ms:")

    @staticmethod
    def get_sheet_meta(sheet_id: int):
        with get_pg_cursor(dict_cursor=True) as cur:
            cur.execute("SELECT * FROM sheets_meta WHERE sheet_id = %s", (sheet_id,))
            row = cur.fetchone()
            if not row:
                return None
            return {
                "sheet_id": row["sheet_id"],
                "name": row["name"],
                "row_count": row["row_count"] or 0,
                "sort_order": row["sort_order"] or 0,
                "tab_color": row["tab_color"] or "",
                "col_styles": json.loads(row["col_styles_json"]) if row["col_styles_json"] else {},
                "col_widths": json.loads(row["col_widths_json"]) if row["col_widths_json"] else {},
                "freeze_rows": row["freeze_rows"] or 0,
                "freeze_cols": row["freeze_cols"] or 0,
                "merges": json.loads(row["merges_json"]) if row["merges_json"] else [],
            }

    @staticmethod
    def add_sheet(name: str):
        with get_pg_cursor() as cur:
            cur.execute("SELECT COALESCE(MAX(sort_order), 0) + 1 FROM sheets_meta")
            next_sort = cur.fetchone()[0]
            cur.execute(
                """
                INSERT INTO sheets_meta (name, row_count, sort_order)
                VALUES (%s, 0, %s)
                RETURNING sheet_id
                """,
                (name, next_sort)
            )
            sheet_id = cur.fetchone()[0]
            ensure_sheet_table(sheet_id)
            SheetService.invalidate_cache()
            return {"sheet_id": sheet_id, "name": name, "row_count": 0, "sort_order": next_sort}

    @staticmethod
    def rename_sheet(sheet_id: int, new_name: str):
        with get_pg_cursor() as cur:
            cur.execute(
                "UPDATE sheets_meta SET name = %s, updated_at = NOW() WHERE sheet_id = %s",
                (new_name, sheet_id)
            )
            cur.execute(
                "UPDATE live_inventory_ledger SET sheet_name = %s WHERE sheet_id = %s",
                (new_name, sheet_id)
            )
        SheetService.invalidate_cache()
        return True

    @staticmethod
    def duplicate_sheet(source_sheet_id: int, new_name: str):
        with get_pg_cursor() as cur:
            # 1. Fetch source metadata
            cur.execute("SELECT * FROM sheets_meta WHERE sheet_id = %s", (source_sheet_id,))
            src = cur.fetchone()
            if not src:
                raise ValueError(f"Source sheet {source_sheet_id} not found")

            cur.execute("SELECT COALESCE(MAX(sort_order), 0) + 1 FROM sheets_meta")
            next_sort = cur.fetchone()[0]

            # 2. Insert new sheet metadata
            cur.execute(
                """
                INSERT INTO sheets_meta (
                    name, row_count, sort_order, tab_color,
                    col_styles_json, col_widths_json, freeze_rows, freeze_cols, merges_json
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING sheet_id
                """,
                (
                    new_name, src[2], next_sort, src[4],
                    src[5], src[6], src[7], src[8], src[9]
                )
            )
            new_id = cur.fetchone()[0]
            ensure_sheet_table(new_id)

            # 3. Copy rows from sheet_{src} to sheet_{new_id}
            cols_str = ", ".join(f'"{c}"' for c in Config.COLS_AZ)
            cur.execute(
                f"""
                INSERT INTO "sheet_{new_id}" (row_idx, {cols_str})
                SELECT row_idx, {cols_str} FROM "sheet_{source_sheet_id}"
                """
            )

            # 4. Copy styles
            cur.execute(
                """
                INSERT INTO sheet_styles (sheet_id, row_idx, col_key, style_json)
                SELECT %s, row_idx, col_key, style_json FROM sheet_styles WHERE sheet_id = %s
                """,
                (new_id, source_sheet_id)
            )

        SheetService.invalidate_cache()
        return {"sheet_id": new_id, "name": new_name}

    @staticmethod
    def delete_sheet(sheet_id: int):
        with get_pg_cursor() as cur:
            cur.execute("DELETE FROM sheets_meta WHERE sheet_id = %s", (sheet_id,))
            cur.execute("DELETE FROM sheet_styles WHERE sheet_id = %s", (sheet_id,))
            cur.execute("DELETE FROM live_inventory_ledger WHERE sheet_id = %s", (sheet_id,))
            cur.execute(f'DROP TABLE IF EXISTS "sheet_{sheet_id}"')
        SheetService.invalidate_cache()
        return True

    @staticmethod
    def set_tab_color(sheet_id: int, color: str):
        with get_pg_cursor() as cur:
            cur.execute("UPDATE sheets_meta SET tab_color = %s WHERE sheet_id = %s", (color, sheet_id))
        SheetService.invalidate_cache()
        return True

    @staticmethod
    def set_freeze(sheet_id: int, freeze_rows: int, freeze_cols: int):
        with get_pg_cursor() as cur:
            cur.execute(
                "UPDATE sheets_meta SET freeze_rows = %s, freeze_cols = %s WHERE sheet_id = %s",
                (freeze_rows, freeze_cols, sheet_id)
            )
        SheetService.invalidate_cache()
        return True

    @staticmethod
    def save_col_widths(sheet_id: int, widths: dict):
        payload = json.dumps(widths or {})
        with get_pg_cursor() as cur:
            cur.execute("UPDATE sheets_meta SET col_widths_json = %s WHERE sheet_id = %s", (payload, sheet_id))
        SheetService.invalidate_cache()
        return True

    @staticmethod
    def toggle_merge(sheet_id: int, merge_range: dict):
        with get_pg_cursor(dict_cursor=True) as cur:
            cur.execute("SELECT merges_json FROM sheets_meta WHERE sheet_id = %s", (sheet_id,))
            row = cur.fetchone()
            merges = json.loads(row["merges_json"]) if row and row["merges_json"] else []
            # toggle logic
            found = False
            for i, m in enumerate(merges):
                if m.get("r1") == merge_range.get("r1") and m.get("c1") == merge_range.get("c1"):
                    del merges[i]
                    found = True
                    break
            if not found:
                merges.append(merge_range)

            cur.execute(
                "UPDATE sheets_meta SET merges_json = %s WHERE sheet_id = %s",
                (json.dumps(merges), sheet_id)
            )
        SheetService.invalidate_cache()
        return merges

