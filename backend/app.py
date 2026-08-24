"""
Flask application entry point.

Local dev:   python app.py
Production:  gunicorn app:app
"""
from __future__ import annotations

import logging

from flask import Flask, jsonify
from flask_cors import CORS

import db
from config import FRONTEND_URL, FLASK_ENV
from routes.schedule_routes import schedule_bp
from routes.order_routes import order_bp
from routes.machine_routes import machine_bp
from routes.disruption_routes import disruption_bp
from routes.strategy_routes import strategy_bp
from routes.misc_routes import misc_bp


def create_app() -> Flask:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    app = Flask(__name__)
    allowed_origins = [FRONTEND_URL, "http://localhost:5173", "http://127.0.0.1:5173"]
    CORS(app, resources={r"/api/*": {"origins": allowed_origins}})

    db.init_db()

    app.register_blueprint(schedule_bp)
    app.register_blueprint(order_bp)
    app.register_blueprint(machine_bp)
    app.register_blueprint(disruption_bp)
    app.register_blueprint(strategy_bp)
    app.register_blueprint(misc_bp)

    @app.errorhandler(404)
    def not_found(_e):
        return jsonify({"success": False, "error": "Not found.",
                         "suggestion": "Check the API path - see README.md for the full endpoint list."}), 404

    @app.errorhandler(405)
    def method_not_allowed(_e):
        return jsonify({"success": False, "error": "Method not allowed.",
                         "suggestion": "Check the HTTP method (GET/POST) for this endpoint."}), 405

    @app.errorhandler(Exception)
    def unhandled_exception(e):
        app.logger.exception("Unhandled exception")
        return jsonify({"success": False, "error": "Internal server error.",
                         "suggestion": "This is unexpected - please check the server logs.",
                         "details": {"type": type(e).__name__}}), 500

    @app.get("/")
    def root():
        return jsonify({"service": "Machine Shop Scheduler API", "status": "running", "env": FLASK_ENV})

    return app


app = create_app()

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    # threaded=True: schedule generation/replan legitimately blocks for up to
    # ~60-90s solving; without this, Werkzeug's dev server serializes ALL
    # requests (even unrelated health checks) behind that one call.
    # use_reloader=False: the debug auto-reloader restarts the process on any
    # detected file change, which aborts an in-flight long-running solve mid-
    # request (surfaces as a plain "Network Error" in the browser with no
    # trace in the Flask log, since the request never got to finish/log). The
    # interactive debugger (debug=True) is still enabled for real error
    # tracebacks; only the file-watching auto-restart is disabled.
    app.run(host="0.0.0.0", port=port, debug=(FLASK_ENV == "development"),
            use_reloader=False, threaded=True)
