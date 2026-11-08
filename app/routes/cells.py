from flask import Blueprint, request, jsonify
from app.services.row_service import RowService

cells_bp = Blueprint("cells", __name__)


@cells_bp.route("/api/update_cell", methods=["POST"])
def update_cell():
    data = request.get_json(silent=True) or {}
    sheet_id = int(data.get("sheet_id") or 1)
    row_idx = int(data.get("row") or data.get("row_idx") or 0)
    col = (data.get("col") or data.get("col_key") or "A").upper()
    val = str(data.get("val") or data.get("value") or "")

    if not row_idx:
        return jsonify({"ok": False, "error": "row index required"}), 400

    try:
        RowService.update_cell(sheet_id, row_idx, col, val)
        return jsonify({"ok": True, "sheet_id": sheet_id, "row": row_idx, "col": col, "val": val})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@cells_bp.route("/api/batch_update_cells", methods=["POST"])
def batch_update_cells():
    data = request.get_json(silent=True) or {}
    sheet_id = int(data.get("sheet_id") or 1)
    updates = data.get("updates") or []
    try:
        count = RowService.batch_update_cells(sheet_id, updates)
        return jsonify({"ok": True, "sheet_id": sheet_id, "updated_cells": count})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@cells_bp.route("/api/update_styles", methods=["POST"])
def update_styles():
    data = request.get_json(silent=True) or {}
    sheet_id = int(data.get("sheet_id") or 1)
    styles = data.get("styles") or []
    try:
        count = RowService.update_styles(sheet_id, styles)
        return jsonify({"ok": True, "sheet_id": sheet_id, "styles_count": count})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@cells_bp.route("/api/clear_styles", methods=["POST"])
def clear_styles():
    data = request.get_json(silent=True) or {}
    sheet_id = int(data.get("sheet_id") or 1)
    r_start = data.get("row_start")
    r_end = data.get("row_end")
    try:
        RowService.clear_styles(
            sheet_id,
            int(r_start) if r_start is not None else None,
            int(r_end) if r_end is not None else None
        )
        return jsonify({"ok": True, "sheet_id": sheet_id})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

