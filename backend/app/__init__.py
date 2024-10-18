# backend/app/__init__.py
import logging
from flask import Flask
from flask_cors import CORS

def create_app():
    app = Flask(__name__)
    CORS(app, resources={r"/*": {"origins": "*"}})  # Enable CORS for all routes

    # Configure logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    app.logger.addHandler(logger)

    with app.app_context():
        from .routes import main
        app.register_blueprint(main)

    return app
