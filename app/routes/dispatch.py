from flask import Blueprint, request, jsonify
from app.services.dispatch_service import DispatchService

dispatch_bp = Blueprint("dispatch", __name__)


def _extract_param(key, default=""):
    data = request.get_json(silent=True) or {}
    val = request.args.get(key)
    if val is None:
        val = request.form.get(key)
    if val is None:
        val = data.get(key, default)
    return str(val).strip() if val is not None else default


@dispatch_bp.route("/api_dispatch", methods=["GET", "POST"])
@dispatch_bp.route("/api_dispatch.php", methods=["GET", "POST"])
@dispatch_bp.route("/telecom_pool_api", methods=["GET", "POST"])
@dispatch_bp.route("/telecom_pool_api.php", methods=["GET", "POST"])
def handle_dispatch():
    action = _extract_param("action") or _extract_param("type") or "pool_counts_quick"
    circle = _extract_param("circle") or _extract_param("Telecom_circles") or _extract_param("state") or ""
    carrier = _extract_param("carrier") or _extract_param("Network_operators") or _extract_param("operator") or ""
    limit = max(1, min(int(_extract_param("limit", "1") or "1"), 50))
    bot_id = _extract_param("bot_id") or _extract_param("rdp_id") or _extract_param("instance_id") or "unknown"

    try:
        if action in ("pool_counts_quick", "stats", "count"):
            res = DispatchService.get_pool_counts(circle=circle, carrier=carrier)
            return jsonify(res)

        elif action in ("fetch_pool", "fetch_next", "lease"):
            res = DispatchService.fetch_pool(circle=circle, carrier=carrier, limit=limit, bot_id=bot_id)
            return jsonify(res)

        elif action in ("report_outcome", "report_result", "update_step_status"):
            sheet_id = int(_extract_param("sheet_id", "1") or 1)
            row_idx = int(_extract_param("row_idx", "0") or 0)
            outcome = _extract_param("outcome") or _extract_param("status") or _extract_param("result")
            if not row_idx:
                return jsonify({"ok": False, "error": "row_idx required"}), 400
            res = DispatchService.report_outcome(sheet_id=sheet_id, row_idx=row_idx, outcome=outcome, bot_id=bot_id)
            return jsonify(res)

        else:
            return jsonify({"ok": False, "error": f"Unknown action: {action}"}), 400

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@dispatch_bp.route("/api/check_disabled", methods=["GET", "POST"])
@dispatch_bp.route("/api_check_disabled.php", methods=["GET", "POST"])
def check_disabled():
    sheet_id = int(_extract_param("sheet_id", "1") or 1)
    row_idx = int(_extract_param("row_idx", "0") or 0)
    outcome = _extract_param("outcome", "DISABLED")
    bot_id = _extract_param("bot_id", "bot_checker")

    if not row_idx:
        return jsonify({"ok": False, "error": "row_idx required"}), 400

    try:
        res = DispatchService.report_outcome(sheet_id=sheet_id, row_idx=row_idx, outcome=outcome, bot_id=bot_id)
        return jsonify(res)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

