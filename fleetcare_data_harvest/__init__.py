import os

from flask import Flask

from .database import db
from .views import bp

dot_env = os.path.join(os.getcwd(), ".env")
if os.path.exists(dot_env):
    from dotenv import load_dotenv

    load_dotenv()


def create_app(app_config=None):
    """The application factory, used to generate the Flask instance."""
    app = Flask(__name__)
    database_url = os.getenv("DATABASE_URL", "sqlite:///:memory:").replace("postgis", "postgresql+psycopg")

    if app_config:
        app.config.update(app_config)
    else:
        app.config["SQLALCHEMY_DATABASE_URI"] = database_url
        app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)

    app.register_blueprint(bp)
    app.add_url_rule("/livez", endpoint="liveness")
    app.add_url_rule("/readyz", endpoint="readiness")
    app.add_url_rule("/", endpoint="index")

    return app
