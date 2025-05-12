import os
import logging
from datetime import datetime

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_socketio import SocketIO
from flask_migrate import Migrate
from sqlalchemy.orm import DeclarativeBase

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# Create base class for SQLAlchemy models
class Base(DeclarativeBase):
    pass

# Initialize extensions
db = SQLAlchemy(model_class=Base)
login_manager = LoginManager()
socketio = SocketIO()
migrate = Migrate()

# Create the app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key")

# Configure the database
database_url = os.environ.get("DATABASE_URL")
# Ensure it uses postgresql:// format instead of postgres:// if needed
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///agri_auction.db"
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Initialize extensions with the app
db.init_app(app)
login_manager.init_app(app)
migrate.init_app(app, db)
login_manager.login_view = 'login'
login_manager.login_message_category = 'info'
socketio.init_app(app, cors_allowed_origins="*")

with app.app_context():
    # Import models
    from models import User, Auction, Bid, Product, Transaction
    
    # Create all tables
    db.create_all()
    
    # Import and register routes
    from routes import register_routes
    register_routes(app)
    
    # Import and register admin views
    from admin import setup_admin
    setup_admin(app)

# Template filters
@app.template_filter('format_datetime')
def format_datetime(value, format='%Y-%m-%d %H:%M:%S'):
    if value is None:
        return ""
    return datetime.strftime(value, format)

@app.template_filter('currency')
def currency_format(value):
    if value is None:
        return "₹0.00"
    return "₹{:,.2f}".format(value)
