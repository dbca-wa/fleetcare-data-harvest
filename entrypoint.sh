#!/bin/bash
gunicorn 'fleetcare_data_harvest:create_app()' --config gunicorn.py
