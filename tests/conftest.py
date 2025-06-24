import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError as SQLAlchemyOperationalError
from sqlalchemy.pool import StaticPool
from sqlalchemy.sql import text

from fleetcare_data_harvest import create_app
from fleetcare_data_harvest.database import db

with open(os.path.join(os.path.dirname(__file__), "schema.sql"), "rb") as f:
    _schema_sql = f.read().decode("utf8")


def pytest_addoption(parser):
    parser.addoption(
        "--dburl",
        action="store",
        default="postgresql+psycopg://user:password@hostname/dbname",
        help="Database URL to use for tests.",
    )


@pytest.fixture(scope="session")
def db_url(request):
    """Fixture to retrieve the database URL."""
    return request.config.getoption("--dburl")


@pytest.hookimpl(tryfirst=True)
def pytest_sessionstart(session):
    db_url = session.config.getoption("--dburl")
    try:
        # Attempt to create an engine and connect to the database.
        engine = create_engine(db_url, poolclass=StaticPool)
        connection = engine.connect()
        connection.close()  # Close the connection right after a successful connect.
    except SQLAlchemyOperationalError:
        pytest.exit("Stopping tests because database connection could not be established.")


@pytest.fixture(scope="session")
def app(db_url):
    """Session-wide test 'app' fixture."""
    test_config = {
        "SQLALCHEMY_DATABASE_URI": db_url,
        "SQLALCHEMY_TRACK_MODIFICATIONS": False,
        "TESTING": True,
        "DEBUG": True,
    }
    app = create_app(test_config)

    with app.app_context():
        # Set up the database table.
        db.session.execute(text(_schema_sql))
        # Install the test fixture data.
        # db.session.execute(text(_data_sql))

        yield app


@pytest.fixture
def test_client(app):
    return app.test_client()
