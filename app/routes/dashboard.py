import time
from flask import Blueprint, request, jsonify
from app.database.connection import check_pg_health
from app.cache.dragonfly import get_dragonfly_telemetry, verify_dragonfly_pipeline
from app.services.dashboard_service import DashboardService

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/health", methods=["GET"])
def health():
    t0 = time.perf_counter()
    pg_status = check_pg_health()
    df_status = get_dragonfly_telemetry()
    elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 2)

    all_healthy = pg_status.get("online", False)

    return jsonify({
        "status": "healthy" if all_healthy else "degraded",
        "total_latency_ms": elapsed_ms,
        "postgresql_16": pg_status,
        "dragonfly_db": df_status,
    }), (200 if all_healthy else 503)


@dashboard_bp.route("/api/dashboard_stats", methods=["GET"])
def dashboard_stats():
    force = request.args.get("force", "0") in ("1", "true", "True") or request.args.get("refresh", "0") in ("1", "true", "True")
    try:
        data = DashboardService.get_dashboard_stats(force_rebuild=force)
        return jsonify(data)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@dashboard_bp.route("/api/sheet_xray", methods=["GET"])
def sheet_xray():
    sheet_id = int(request.args.get("sheet_id", 1))
    try:
        data = DashboardService.get_sheet_xray(sheet_id)
        return jsonify({"ok": True, **data})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@dashboard_bp.route("/api/dragonfly_status", methods=["GET"])
def dragonfly_status():
    try:
        telemetry = get_dragonfly_telemetry()
        return jsonify({"ok": True, "telemetry": telemetry})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@dashboard_bp.route("/api/benchmark", methods=["GET"])
def benchmark():
    num_ops = int(request.args.get("ops", 100))
    res = verify_dragonfly_pipeline(num_ops=num_ops)
    return jsonify(res)

