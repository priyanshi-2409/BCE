#Student_ID_25017334_Name_Priyanshi_Jadeja

from flask import Flask
from datetime import datetime


def create_app():
    app = Flask(__name__)
    app.secret_key = "supersecretkey"  

    # JINJA FILTERS

    def format_date(value):
        if not value:
            return ""
        try:
            dt = datetime.strptime(str(value), "%Y-%m-%d")
            return dt.strftime("%d %b %Y")
        except:
            return value

    def format_datetime(value):
        if not value:
            return ""
        try:
            dt = datetime.strptime(str(value), "%Y-%m-%d %H:%M:%S")
            return dt.strftime("%d %b %Y, %H:%M")
        except:
            return value

    def format_time(value):
        if not value:
            return "-"
        try:
            t = datetime.strptime(str(value), "%H:%M:%S")
            return t.strftime("%H:%M")
        except:
            return value

    def money(value):
        try:
            return f"{value:.2f}"
        except:
            return value

    # Register filters
    app.jinja_env.filters["format_date"] = format_date
    app.jinja_env.filters["format_datetime"] = format_datetime
    app.jinja_env.filters["format_time"] = format_time
    app.jinja_env.filters["money"] = money

    # BLUEPRINTS

    from app.routes.home import home_bp
    from app.routes.events import events_bp
    from app.routes.auth import auth_bp
    from app.routes.booking import booking_bp
    from app.routes.admin import admin_bp

    app.register_blueprint(home_bp)
    app.register_blueprint(events_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(booking_bp)
    app.register_blueprint(admin_bp, url_prefix="/admin")

    return app