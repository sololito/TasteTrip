# app/__init__.py
import os
from flask import Flask
from dotenv import load_dotenv

def create_app():
    # Load environment variables
    load_dotenv()

    app = Flask(__name__, template_folder='../templates', static_folder='../static')
    app.secret_key = os.urandom(24)

    # Register blueprints/routes
    from .routes import main
    app.register_blueprint(main)

    return app