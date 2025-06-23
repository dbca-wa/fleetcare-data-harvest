#!/bin/bash
gunicorn 'fleetcare-data-harvest:create_app()' --config gunicorn.py
