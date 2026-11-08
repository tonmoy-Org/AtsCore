from flask import Blueprint, request, jsonify
from app.services.row_service import RowService

rows_bp = Blueprint("rows", __name__)


@rows_bp.route("/api/rows", methods=["GET"])
def get_rows():
    try:
        sheet_id = int(request.args.get("sheet_id", 1))
        offset = int(request.args.get("offset", 0))
        limit = min(int(request.args.get("limit", 1000)), 5000)
        search = request.args.get("q", "").strip()

        data = RowService.get_rows(sheet_id=sheet_id, offset=offset, limit=limit, search=search)
        return jsonify({"ok": True, **data})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@rows_bp.route("/api/insert_row", methods=["POST"])
def insert_row():
    data = request.get_json(silent=True) or {}
    sheet_id = int(data.get("sheet_id") or 1)
    row_idx = int(data.get("row_idx") or 2)
    try:
        RowService.insert_row(sheet_id, row_idx)
        return jsonify({"ok": True, "sheet_id": sheet_id, "row_idx": row_idx})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@rows_bp.route("/api/delete_rows", methods=["POST"])
def delete_rows():
    data = request.get_json(silent=True) or {}
    sheet_id = int(data.get("sheet_id") or 1)
    rows = data.get("rows") or []
    if not rows and "row_idx" in data:
        rows = [int(data["row_idx"])]
    try:
        deleted = RowService.delete_rows(sheet_id, rows)
        return jsonify({"ok": True, "deleted_count": deleted})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@rows_bp.route("/api/sort_sheet", methods=["POST"])
def sort_sheet():
    data = request.get_json(silent=True) or {}
    sheet_id = int(data.get("sheet_id") or 1)
    col_key = (data.get("col_key") or "A").upper()
    ascending = bool(data.get("ascending", True))
    try:
        RowService.sort_sheet(sheet_id, col_key, ascending)
        return jsonify({"ok": True, "sorted_by": col_key, "ascending": ascending})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

