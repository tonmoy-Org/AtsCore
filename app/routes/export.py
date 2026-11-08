import io
import csv
from flask import Blueprint, request, Response, jsonify
from app.config import Config
from app.database.connection import get_pg_cursor

export_bp = Blueprint("export", __name__)


@export_bp.route("/api/export_tsv", methods=["GET"])
@export_bp.route("/api/export_csv", methods=["GET"])
def export_file():
    sheet_id = int(request.args.get("sheet_id", 1))
    is_csv = request.path.endswith("export_csv")
    delimiter = "," if is_csv else "\t"
    mimetype = "text/csv" if is_csv else "text/tab-separated-values"
    ext = "csv" if is_csv else "tsv"

    table_name = f"sheet_{sheet_id}"
    cols_str = ", ".join(f'"{c}"' for c in Config.COLS_AZ)

    with get_pg_cursor(dict_cursor=False) as cur:
        # Check sheet name
        cur.execute("SELECT name FROM sheets_meta WHERE sheet_id = %s", (sheet_id,))
        meta = cur.fetchone()
        sheet_name = meta[0] if meta else f"Sheet_{sheet_id}"

        cur.execute(f'SELECT {cols_str} FROM "{table_name}" ORDER BY row_idx ASC')
        rows = cur.fetchall()

    output = io.StringIO()
    writer = csv.writer(output, delimiter=delimiter, lineterminator="\n")
    for r in rows:
        # Trim empty trailing cells
        row_list = list(r)
        while row_list and not row_list[-1]:
            row_list.pop()
        writer.writerow(row_list)

    resp = Response(output.getvalue(), mimetype=mimetype)
    resp.headers["Content-Disposition"] = f'attachment; filename="{sheet_name}.{ext}"'
    return resp


@export_bp.route("/api/import_working_txt", methods=["POST"])
def import_working_txt():
    # Placeholder for importing working text accounts into current sheet
    data = request.get_json(silent=True) or {}
    sheet_id = int(data.get("sheet_id") or 1)
    text_content = data.get("content", "")
    lines = [l.strip() for l in text_content.splitlines() if l.strip()]

    if not lines:
        return jsonify({"ok": False, "error": "No content provided"}), 400

    table_name = f"sheet_{sheet_id}"
    with get_pg_cursor() as cur:
        cur.execute(f'SELECT COALESCE(MAX(row_idx), 1) FROM "{table_name}"')
        start_idx = cur.fetchone()[0] + 1

        for i, line in enumerate(lines):
            parts = line.split()
            a_val = parts[0] if len(parts) > 0 else ""
            b_val = parts[1] if len(parts) > 1 else ""
            cur.execute(
                f'INSERT INTO "{table_name}" (row_idx, "A", "B") VALUES (%s, %s, %s)',
                (start_idx + i, a_val, b_val)
            )

    return jsonify({"ok": True, "sheet_id": sheet_id, "imported_rows": len(lines)})

