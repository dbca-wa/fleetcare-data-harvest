#!/bin/bash
hypercorn 'fleetcare-data-harvest:create_app()' --config hypercorn.toml
