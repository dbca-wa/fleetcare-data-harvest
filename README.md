# Fleetcare data harvest service

A basic web service to act as a webhook for an Azure EventGrid subscription (BlobCreated events),
ingest data from uploaded blobs, and create tracking data within the Resource Tracking database.

## Installation

The recommended way to set up this project for development is using
[Poetry](https://python-poetry.org/docs/) to install and manage a virtual Python
environment. With Poetry installed, change into the project directory and run:

    poetry install

Activate the virtualenv like so:

    poetry shell

To run Python commands in the virtualenv, thereafter run them like so:

    python manage.py

Manage new or updating project dependencies with Poetry also, like so:

    poetry add newpackage==1.0

## Environment variables

This project uses **python-dotenv** to set environment variables (in a `.env` file):

    PORT=8080  # Optional
    DATABASE_URL=postgis://USER:PASSWORD@HOST:5432/DATABASE_NAME
    AZURE_STORAGE_CONNECTION_STRING=AzureConnectionString
    AZURE_CONTAINER=container

## Running

Run a local copy of the application like so:

    python fleetcare_data_harvest.py

The application runs on port 8080 by default. To change this, set an environment
variable value for `PORT`.

## Docker image

To build a new Docker image from the `Dockerfile`:

    docker image build -t ghcr.io/dbca-wa/fleetcare-data-harvest .

## Pre-commit hooks

This project includes the following pre-commit hooks:

- TruffleHog (credential scanning): <https://github.com/marketplace/actions/trufflehog-oss>

Pre-commit hooks may have additional system dependencies to run. Optionally
install pre-commit hooks locally like so (with the virtualenv activated first):

    pre-commit install

Reference: <https://pre-commit.com/>
