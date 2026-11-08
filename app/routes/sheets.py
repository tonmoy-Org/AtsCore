from flask import Blueprint, request, jsonify
from app.services.sheet_service import SheetService

sheets_bp = Blueprint("sheets", __name__)


@sheets_bp.route("/api/sheets", methods=["GET"])
def get_sheets():
    try:
        sheets = SheetService.get_all_sheets()
        return jsonify({"ok": True, "sheets": sheets})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@sheets_bp.route("/api/add_sheet", methods=["POST"])
def add_sheet():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or request.form.get("name") or "").strip()
    if not name:
        return jsonify({"ok": False, "error": "Sheet name is required"}), 400
    try:
        result = SheetService.add_sheet(name)
        return jsonify({"ok": True, "sheet": result})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@sheets_bp.route("/api/rename_sheet", methods=["POST"])
def rename_sheet():
    data = request.get_json(silent=True) or {}
    sheet_id = int(data.get("sheet_id") or request.form.get("sheet_id") or 0)
    new_name = (data.get("name") or request.form.get("name") or "").strip()
    if not sheet_id or not new_name:
        return jsonify({"ok": False, "error": "sheet_id and name required"}), 400
    try:
        SheetService.rename_sheet(sheet_id, new_name)
        return jsonify({"ok": True, "sheet_id": sheet_id, "name": new_name})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@sheets_bp.route("/api/duplicate_sheet", methods=["POST"])
def duplicate_sheet():
    data = request.get_json(silent=True) or {}
    sheet_id = int(data.get("sheet_id") or request.form.get("sheet_id") or 0)
    new_name = (data.get("name") or request.form.get("name") or f"Copy of Sheet {sheet_id}").strip()
    if not sheet_id:
        return jsonify({"ok": False, "error": "sheet_id required"}), 400
    try:
        result = SheetService.duplicate_sheet(sheet_id, new_name)
        return jsonify({"ok": True, "sheet": result})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@sheets_bp.route("/api/delete_sheet", methods=["POST"])
def delete_sheet():
    data = request.get_json(silent=True) or {}
    sheet_id = int(data.get("sheet_id") or request.form.get("sheet_id") or 0)
    if not sheet_id:
        return jsonify({"ok": False, "error": "sheet_id required"}), 400
    try:
        SheetService.delete_sheet(sheet_id)
        return jsonify({"ok": True, "deleted_sheet_id": sheet_id})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@sheets_bp.route("/api/set_tab_color", methods=["POST"])
def set_tab_color():
    data = request.get_json(silent=True) or {}
    sheet_id = int(data.get("sheet_id") or request.form.get("sheet_id") or 0)
    color = (data.get("tab_color") or data.get("color") or "").strip()
    try:
        SheetService.set_tab_color(sheet_id, color)
        return jsonify({"ok": True, "sheet_id": sheet_id, "color": color})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@sheets_bp.route("/api/set_freeze", methods=["POST"])
def set_freeze():
    data = request.get_json(silent=True) or {}
    sheet_id = int(data.get("sheet_id") or 0)
    rows = int(data.get("freeze_rows", 0))
    cols = int(data.get("freeze_cols", 0))
    try:
        SheetService.set_freeze(sheet_id, rows, cols)
        return jsonify({"ok": True, "freeze_rows": rows, "freeze_cols": cols})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@sheets_bp.route("/api/save_col_widths", methods=["POST"])
def save_col_widths():
    data = request.get_json(silent=True) or {}
    sheet_id = int(data.get("sheet_id") or 0)
    widths = data.get("col_widths") or {}
    try:
        SheetService.save_col_widths(sheet_id, widths)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@sheets_bp.route("/api/toggle_merge", methods=["POST"])
def toggle_merge():
    data = request.get_json(silent=True) or {}
    sheet_id = int(data.get("sheet_id") or 0)
    merge_range = data.get("range") or {}
    try:
        merges = SheetService.toggle_merge(sheet_id, merge_range)
        return jsonify({"ok": True, "merges": merges})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

