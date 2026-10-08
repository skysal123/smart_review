import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from dotenv import load_dotenv
from google import genai

# Load .env from the parent directory since our app is in a subfolder
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

db = SQLAlchemy()
migrate = Migrate()

def create_app():
    app = Flask(__name__)

    # Configuration
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///reviews.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['GEMINI_API_KEY'] = os.getenv('GEMINI_API_KEY')
    app.config['ADMIN_USERNAME'] = os.getenv('ADMIN_USERNAME')
    app.config['ADMIN_PASSWORD'] = os.getenv('ADMIN_PASSWORD')
    app.config['APP_BASE_URL'] = os.getenv('APP_BASE_URL', 'http://127.0.0.1:5000')

    db.init_app(app)
    migrate.init_app(app, db)

    # Initialize Gemini Client once
    try:
        client = genai.Client(api_key=app.config['GEMINI_API_KEY'])
        app.extensions['gemini_client'] = client
    except Exception as e:
        app.logger.error(f"Failed to initialize Gemini client: {e}")

    from app.routes import main_bp
    app.register_blueprint(main_bp)

    return app
