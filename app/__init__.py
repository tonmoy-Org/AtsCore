import logging
from flask import Flask, jsonify

try:
    from flask_cors import CORS
except ImportError:
    CORS = None

from app.config import Config
from app.database import init_pg_pool, init_enterprise_schema
from app.routes import sheets_bp, rows_bp, cells_bp, dispatch_bp, dashboard_bp, export_bp

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s in %(name)s: %(message)s"
)
logger = logging.getLogger("atscore")


def create_app(config_class=Config):
    """
    Application Factory for AtsCore Enterprise Backend.
    """
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Enable CORS for frontend clients / dashboards
    if CORS:
        CORS(app, resources={r"/*": {"origins": "*"}})
    else:
        @app.after_request
        def add_cors_headers(response):
            response.headers["Access-Control-Allow-Origin"] = "*"
            response.headers["Access-Control-Allow-Headers"] = "Content-Type,Authorization"
            response.headers["Access-Control-Allow-Methods"] = "GET,PUT,POST,DELETE,OPTIONS"
            return response

    # Register Blueprints
    app.register_blueprint(sheets_bp)
    app.register_blueprint(rows_bp)
    app.register_blueprint(cells_bp)
    app.register_blueprint(dispatch_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(export_bp)

    @app.route("/", methods=["GET"])
    def index():
        return jsonify({
            "service": "AtsCore Enterprise Backend",
            "version": "2.0.2",
            "status": "online",
            "endpoints": [
                "/health",
                "/api/sheets",
                "/api/rows",
                "/api/dashboard_stats",
                "/api/dragonfly_status",
                "/api_dispatch.php",
            ]
        })

    @app.errorhandler(404)
    def handle_not_found(e):
        return jsonify({"ok": False, "error": "Endpoint not found"}), 404

    @app.errorhandler(500)
    def handle_internal_error(e):
        logger.error(f"Internal server error: {e}", exc_info=True)
        return jsonify({"ok": False, "error": "Internal server error"}), 500

    return app
