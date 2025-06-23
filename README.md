# Fleetcare data harvest service

A basic web service to act as a webhook for an Azure EventGrid subscription (BlobCreated events),
ingest data from uploaded blobs, and create tracking data within the Resource Tracking database.

## Installation

This project uses [uv](https://docs.astral.sh/uv/) to manage and install Python dependencies.
With uv installed, install the required Python version (see `pyproject.toml`). Example:

    uv python install 3.13

Change into the project directory and run:

    uv python pin 3.13
    uv sync

Activate the virtualenv like so:

    source .venv/bin/activate

To run Python commands in the activated virtualenv, thereafter run them like so:

    python manage.py

Manage new or updated project dependencies with uv also, like so:

    uv add newpackage==1.0

## Environment variables

This project uses **python-dotenv** to set environment variables (in a `.env` file):

    DATABASE_URL=postgis://USER:PASSWORD@HOST:5432/DATABASE_NAME
    AZURE_STORAGE_CONNECTION_STRING=AzureConnectionString
    AZURE_CONTAINER=container

## Usage

Run a local copy of the application like so:

    flask --app fleetcare-data-harvest run --debug --port 8080 --reload
    # Serve via Gunicorn:
    gunicorn 'fleetcare-data-harvest:create_app()' --config gunicorn.py --reload

## Testing

Set up a test database (if required), and run unit tests using `pytest`:

    pytest -s --dburl postgresql+psycopg://user:password@hostname/dbname

## Docker image

To build a new Docker image from the `Dockerfile`:

    docker image build -t ghcr.io/dbca-wa/fleetcare-data-harvest .

## Pre-commit hooks

This project includes the following pre-commit hooks:

- TruffleHog (credential scanning): <https://github.com/marketplace/actions/trufflehog-oss>

Pre-commit hooks may have additional system dependencies to run. Optionally
install pre-commit hooks locally like so (with the virtualenv activated first):

    pre-commit install
