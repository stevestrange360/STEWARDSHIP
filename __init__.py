from flask import Flask
from .db import init_db, SessionLocal
from .routes import bp
import os
from dotenv import load_dotenv

load_dotenv()

def create_app():
    app = Flask(__name__)
    app.secret_key = os.getenv("SECRET_KEY", "dev-secret-key-2024")
    
    # Initialize database
    init_db(os.getenv("DATABASE_URL"))
    
    # Register blueprint
    app.register_blueprint(bp)
    
    # Make session available to routes
    app.db_session = SessionLocal
    
    return app