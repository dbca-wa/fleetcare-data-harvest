# Copilot Instructions – fleetcare-data-harvest

## Project Overview

A Flask-based webhook service that receives Azure EventGrid `BlobCreated` events, downloads JSON telemetry blobs from Azure Blob Storage, and upserts vehicle tracking records into a PostgreSQL/PostGIS database (the **Resource Tracking** database).

**Python:** ≥ 3.13  
**Package manager:** [uv](https://docs.astral.sh/uv/)  
**Served via:** Gunicorn on port 8080

---

## Repository Layout

```
fleetcare_data_harvest/   # Main application package
  __init__.py             # App factory (create_app)
  database.py             # Raw SQL helpers via SQLAlchemy Core
  utils.py                # Business logic, Azure blob helpers, logging
  views.py                # Flask Blueprint + HTTP route handlers
tests/
  conftest.py             # pytest fixtures, --dburl CLI option
  schema.sql              # Minimal DB schema for test setup
  data.json               # Sample Fleetcare telemetry payload
  test_factory.py         # App-level config tests
  test_utils.py           # Unit tests for handle_blob_created_event
  test_views.py           # HTTP endpoint tests (liveness, readiness)
gunicorn.py               # Gunicorn configuration (4 workers, port 8080)
Dockerfile                # Multi-stage build using uv
pyproject.toml            # Project metadata, deps, ruff config
```

---

## Key Modules & Functions

### `fleetcare_data_harvest/__init__.py`

- **`create_app(app_config=None) -> Flask`** — Application factory. Reads `DATABASE_URL` env var, initialises Flask-SQLAlchemy, registers the Blueprint, and adds `/livez`, `/readyz`, and `/` URL rules. Pass `app_config` dict to override settings (used in tests).

### `fleetcare_data_harvest/views.py`

- **`GET /livez`** — Liveness probe; returns `"OK"`.
- **`GET /readyz`** — Readiness probe; executes `SELECT 1` against the DB; returns `"OK"` or HTTP 500.
- **`POST /`** — Webhook entry point. Accepts JSON arrays of EventGrid events. Handles:
  - **Subscription validation** (`validationCode` handshake).
  - **`Microsoft.Storage.BlobCreated`** events: downloads the blob, parses JSON, calls `handle_blob_created_event`.

### `fleetcare_data_harvest/utils.py`

- **`configure_logging() -> Logger`** — Sets up stdout logging at INFO level with `{asctime} | {levelname} | {message}` format; sets Azure SDK loggers to WARNING.
- **`get_blob_client(blob_url, conn_str=None, container_name=None) -> BlobClient | None`** — Validates that `blob_url` is on `dbcafleetcaredata.blob.core.windows.net`, then builds an authenticated `BlobClient` using `AZURE_STORAGE_CONNECTION_STRING` and `AZURE_CONTAINER` env vars. Returns `None` for untrusted URLs.
- **`handle_blob_created_event(data, blob_url, logger=None) -> True | None`** — Core business logic:
  1. Extracts `vehicleID` (prefixed `fc_`), `vehicleRego`, GPS coords, heading/velocity/altitude, and `timestamp` (format `%d/%m/%Y %I:%M:%S %p`, localised to `Australia/Perth`).
  2. Calls `get_device` to check whether the device exists.
  3. If exists: optionally `update_device_registration` (if rego changed) and `update_device_details` (if the new point is more recent than `device.seen` and ≤ now AWST).
  4. If not: calls `create_device` with sensible defaults (`symbol="other"`, `district="OTH"`, etc.).
  5. Always calls `create_loggedpoint` to append the tracking record.

### `fleetcare_data_harvest/database.py`

All functions use SQLAlchemy Core (`text()` + `bindparams()`); no ORM models.

| Function                                                                                   | Description                                                                       |
| ------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------- |
| `get_device(deviceid, source_device_type="fleetcare")`                                     | SELECT by `deviceid`; returns `Row(id, seen, registration, deviceid)` or `None`.  |
| `update_device_registration(id, registration)`                                             | UPDATE `registration` for a device PK.                                            |
| `update_device_details(id, seen, point_wkt, velocity, altitude, heading)`                  | UPDATE location/telemetry fields; point stored as PostGIS `geometry(Point,4326)`. |
| `create_device(deviceid, registration, seen, point_wkt, heading, velocity, altitude, ...)` | INSERT into `tracking_device`; `source_device_type` defaults to `"fleetcare"`.    |
| `create_loggedpoint(point_wkt, heading, velocity, altitude, seen, id, blob_url, ...)`      | INSERT into `tracking_loggedpoint`; `raw` column stores the source blob URL.      |

---

## Database Schema

Two tables in the Resource Tracking PostgreSQL/PostGIS database:

- **`tracking_device`** — One row per unique device. Spatial column `point geometry(Point,4326)`. Key columns: `deviceid`, `registration`, `seen`, `source_device_type`.
- **`tracking_loggedpoint`** — Append-only telemetry log. `raw` stores the Azure blob URL as provenance.

Device IDs from Fleetcare are always prefixed with `fc_` to avoid collisions with other source types.

---

## Environment Variables

| Variable                          | Description                                                                      |
| --------------------------------- | -------------------------------------------------------------------------------- |
| `DATABASE_URL`                    | SQLAlchemy connection string, e.g. `postgresql+psycopg://USER:PASS@HOST:5432/DB` |
| `AZURE_STORAGE_CONNECTION_STRING` | Azure Storage connection string                                                  |
| `AZURE_CONTAINER`                 | Azure Blob container name                                                        |

Loaded automatically from a `.env` file if present (via `python-dotenv`).

---

## Conventions

- **No ORM models** — all DB access uses raw SQL via `sqlalchemy.sql.text()` with named `bindparams`. Do not introduce ORM models.
- **App factory pattern** — always use `create_app()` to instantiate Flask; never create a module-level app instance.
- **Type hints** — use standard library types (`str | None`, `Literal[True]`, etc.); no `Optional` from `typing`.
- **Linting** — [Ruff](https://docs.astral.sh/ruff/) with `line-length = 140`, `indent-width = 4`. Ignores E501 (line length) and E722 (bare except).
- **Timezone** — all timestamps are localised to `Australia/Perth` (`ZoneInfo("Australia/Perth")`); use `datetime.astimezone(TZ)` consistently.
- **Geometry** — spatial points are constructed as WKT strings (`POINT(lon lat)`) and stored using `ST_SetSRID(ST_GeomFromText(...), 4326)`.
- **Logging** — pass the `logger` returned by `configure_logging()` into business-logic functions rather than using module-level loggers.
- **Security** — blob URLs are validated against the expected Azure hostname before any download. The TruffleHog pre-commit hook scans for credentials on every commit and push.

---

## Testing

- Tests require a live PostgreSQL database (PostGIS enabled). Pass it via `--dburl`:

  ```
  pytest -s --pdb --dburl postgresql+psycopg://user:password@hostname/dbname
  ```

- `conftest.py` creates the schema from `tests/schema.sql` at session start.
- Test fixtures randomise `vehicleID` to avoid cross-test conflicts.
- No mocking of the database layer; tests run against a real DB.

---

## Running Locally

```bash
uv sync
source .venv/bin/activate

# Dev server
flask --app fleetcare_data_harvest run --debug --port 8080 --reload

# Production-like (Gunicorn)
gunicorn 'fleetcare_data_harvest:create_app()' --config gunicorn.py --reload
```

---

## Docker

```bash
docker image build -t ghcr.io/dbca-wa/fleetcare-data-harvest .
```

The image runs as a non-root user on port 8080, uses uv for dependency installation, and removes dev tooling from the final image.
