import json
import logging
from app.config import Config
from app.database.connection import get_pg_cursor, get_pg_connection
from app.cache.dragonfly import acquire_lock, release_lock, cache_get_json, cache_set_json
from app.services.operator_resolver import clean_state_name, normalize_operator_name, classify_row_status

logger = logging.getLogger("atscore.dispatch")

# Circle to sheet lookup mapping
BOT_CIRCLE_TO_SHEET_MAP = {
    "andhra_pradesh": "Andhra Pradesh ok",
    "andhra pradesh": "Andhra Pradesh ok",
    "assam": "Assam",
    "bihar": "Bihar & Jharkhand",
    "bihar & jharkhand": "Bihar & Jharkhand",
    "delhi": "Delhi",
    "up_east": "East Uttar Pradesh",
    "east uttar pradesh": "East Uttar Pradesh",
    "gujarat": "Gujarat",
    "haryana": "Haryana ok",
    "himachal_pradesh": "Himachal Pradesh",
    "jammu_kashmir": "Jammu & Kashmir",
    "karnataka": "Karnataka",
    "kerala": "Kerala",
    "kolkata": "Kolkata ok",
    "madhya_pradesh": "Madhya Pradesh & Chhattisgarh ok",
    "madhya pradesh": "Madhya Pradesh & Chhattisgarh ok",
    "maharashtra": "Maharashtra & Goa",
    "mumbai": "Mumbai",
    "north_east": "North East",
    "odisha": "Odisha",
    "punjab": "Punjab",
    "rajasthan": "Rajasthan",
    "tamil_nadu": "Tamil Nadu",
    "telangana": "Telangana",
    "west_bengal": "West Bengal",
    "up_west": "West Uttar Pradesh",
    "west uttar pradesh": "West Uttar Pradesh",
}


class DispatchService:
    @staticmethod
    def resolve_sheet_id_for_circle(circle: str):
        c_clean = str(circle or "").strip().lower()
        sheet_target_name = BOT_CIRCLE_TO_SHEET_MAP.get(c_clean, "")

        with get_pg_cursor(dict_cursor=True) as cur:
            if sheet_target_name:
                cur.execute(
                    "SELECT sheet_id, name FROM sheets_meta WHERE name ILIKE %s LIMIT 1",
                    (f"%{sheet_target_name}%",)
                )
                res = cur.fetchone()
                if res:
                    return res["sheet_id"], res["name"]

            # Fallback direct lookup
            cur.execute(
                "SELECT sheet_id, name FROM sheets_meta WHERE name ILIKE %s LIMIT 1",
                (f"%{circle}%",)
            )
            res = cur.fetchone()
            if res:
                return res["sheet_id"], res["name"]

        return 1, "DefaultSheet"

    @staticmethod
    def get_pool_counts(circle: str = "", carrier: str = ""):
        """Returns clean uncolored count + colored count for requested parameters."""
        sheet_id, sheet_name = DispatchService.resolve_sheet_id_for_circle(circle)

        with get_pg_cursor(dict_cursor=True) as cur:
            cur.execute(
                """
                SELECT operator, total_rows, colored_rows, available_rows
                FROM live_inventory_ledger
                WHERE sheet_id = %s
                """,
                (sheet_id,)
            )
            rows = cur.fetchall()

            total_avail = sum(r["available_rows"] for r in rows) if rows else 0
            total_colored = sum(r["colored_rows"] for r in rows) if rows else 0

            return {
                "ok": True,
                "sheet_id": sheet_id,
                "sheet_name": sheet_name,
                "circle": circle,
                "carrier": carrier,
                "total_available": total_avail,
                "total_colored": total_colored,
                "breakdown": rows
            }

    @staticmethod
    def fetch_pool(circle: str = "", carrier: str = "", limit: int = 1, bot_id: str = "unknown"):
        """
        Atomically leases uncolored phone rows for telecom verification bots.
        Guarantees zero-collision across concurrent bot workers using DragonflyDB distributed locks.
        """
        sheet_id, sheet_name = DispatchService.resolve_sheet_id_for_circle(circle)
        lock_key = f"lease:{sheet_id}:{carrier.lower()}"
        lock_token = acquire_lock(lock_key, ttl_ms=10000)

        table_name = f"sheet_{sheet_id}"

        try:
            with get_pg_connection() as conn:
                with conn.cursor() as cur:
                    # Select uncolored rows (rows not present in sheet_styles with colored bg)
                    cur.execute(
                        f"""
                        SELECT s.row_idx, s."A", s."B", s."C", s."D", s."E"
                        FROM "{table_name}" s
                        LEFT JOIN sheet_styles st 
                            ON st.sheet_id = %s AND st.row_idx = s.row_idx AND st.col_key = 'A'
                        WHERE s.row_idx > 1
                          AND (st.style_json IS NULL OR st.style_json NOT LIKE '%%#fff2cc%%')
                        ORDER BY s.row_idx ASC
                        LIMIT %s
                        FOR UPDATE SKIP LOCKED
                        """,
                        (sheet_id, limit)
                    )
                    rows = cur.fetchall()

                    if not rows:
                        return {"ok": False, "count": 0, "accounts": [], "message": "No available stock"}

                    leased_accounts = []
                    lease_style_json = json.dumps({"bg": "#fff2cc", "status": "LEASED", "bot_id": bot_id})

                    for r in rows:
                        r_idx, num, pwd, v_type, st_op, op = r
                        # Mark as leased with #fff2cc in sheet_styles
                        cur.execute(
                            """
                            INSERT INTO sheet_styles (sheet_id, row_idx, col_key, style_json)
                            VALUES (%s, %s, 'A', %s)
                            ON CONFLICT (sheet_id, row_idx, col_key) DO UPDATE SET
                                style_json = EXCLUDED.style_json
                            """,
                            (sheet_id, r_idx, lease_style_json)
                        )
                        # Record in audit lease log
                        cur.execute(
                            """
                            INSERT INTO telecom_bot_lease_log 
                                (bot_id, sheet_id, sheet_name, row_idx, phone_number, carrier, circle, status)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, 'LEASED')
                            """,
                            (bot_id, sheet_id, sheet_name, r_idx, num, carrier, circle)
                        )
                        leased_accounts.append({
                            "sheet_id": sheet_id,
                            "sheet_name": sheet_name,
                            "row_idx": r_idx,
                            "number": num,
                            "password": pwd,
                            "type": v_type,
                            "state_operator": st_op,
                            "operator": op,
                        })

                conn.commit()

            return {
                "ok": True,
                "count": len(leased_accounts),
                "accounts": leased_accounts,
                "bot_id": bot_id,
            }
        finally:
            if lock_token:
                release_lock(lock_key, lock_token)

    @staticmethod
    def report_outcome(sheet_id: int, row_idx: int, outcome: str, bot_id: str = "unknown"):
        """
        Updates account state based on worker outcome:
        - RECOVERED/COMPLETE: Marks cell green (#d9ead3)
        - FAILED/DISABLED: Marks cell red (#f4cccc)
        - INACTIVE/RETRY: Clears styling so it returns to pool
        """
        category, sub_reason = classify_row_status(outcome)
        style_color = None
        if category == "COMPLETE":
            style_color = "#d9ead3"  # Soft green
        elif category == "FAILED":
            style_color = "#f4cccc"  # Soft red

        table_name = f"sheet_{sheet_id}"
        with get_pg_cursor() as cur:
            if style_color:
                payload = json.dumps({"bg": style_color, "outcome": outcome, "bot_id": bot_id})
                cur.execute(
                    """
                    INSERT INTO sheet_styles (sheet_id, row_idx, col_key, style_json)
                    VALUES (%s, %s, 'A', %s)
                    ON CONFLICT (sheet_id, row_idx, col_key) DO UPDATE SET
                        style_json = EXCLUDED.style_json
                    """,
                    (sheet_id, row_idx, payload)
                )
            else:
                # Clear lease style so account is available again
                cur.execute(
                    "DELETE FROM sheet_styles WHERE sheet_id = %s AND row_idx = %s AND col_key = 'A'",
                    (sheet_id, row_idx)
                )

            # Update lease log
            cur.execute(
                """
                UPDATE telecom_bot_lease_log
                SET status = %s, completed_at = NOW()
                WHERE sheet_id = %s AND row_idx = %s AND bot_id = %s
                """,
                (category, sheet_id, row_idx, bot_id)
            )

        return {"ok": True, "sheet_id": sheet_id, "row_idx": row_idx, "status": category}

