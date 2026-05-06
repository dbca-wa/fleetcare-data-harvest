import json
from datetime import datetime

from flask import Blueprint, abort, request
from sqlalchemy.sql import text

from .database import db
from .utils import TZ, configure_logging, get_blob_client, handle_blob_created_event

bp = Blueprint("fleetcare_data_harvest", __name__)
logger = configure_logging()


@bp.get("/livez")
def liveness():
    return "OK"


@bp.get("/readyz")
def readiness():
    # Returns a HTTP 500 error if database connection unavailable.
    db.session.execute(text("SELECT 1")).fetchone()
    return "OK"


@bp.post("/")
def index():
    """Webhook endpoint to receive events for an Azure Event Grid subscription, being creation of new blobs
    containing device tracking data. The endpoint handles both event subscription (required on creation or
    update of subscriptions) and BlobCreated events.
    NOTE: authentication is provided by our external SSO service (Auth2), hence there is access control on this view.
    """
    if request.is_json:
        data = request.get_json()

        for event in data:
            # Handle initial event subscription validation.
            # https://learn.microsoft.com/en-us/azure/event-grid/webhook-event-delivery#validation-details.
            if "data" in event and "validationCode" in event["data"]:
                validation_code = event["data"]["validationCode"]
                return {"validationResponse": validation_code}
            # Handle BlobCreated events.
            elif "eventType" in event and event["eventType"] == "Microsoft.Storage.BlobCreated":
                # Validation
                if "url" not in event["data"]:
                    abort(400, "Invalid request")

                blob_url = event["data"]["url"]
                blob_client = get_blob_client(blob_url)

                if not blob_client:  # We didn't instantiate a blob client.
                    abort(400, "Invalid request")

                # Check blob properties before downloading.
                blob_properties = blob_client.get_blob_properties()

                # Sanity check: if the blob size is greater than 100 Kb, abort.
                if blob_properties.size >= 1024 * 100:
                    abort(400, "Invalid data")

                blob_content = blob_client.download_blob().read()

                try:
                    data = json.loads(blob_content)
                except:
                    # Catch any exceptions here, e.g. a non-JSON blob
                    abort(400, "Unable to deserialise blob content")

                # Validate the deserialised blob data.
                if "vehicleID" not in data:
                    abort(400, "Invalid data")
                elif "vehicleRego" not in data:
                    abort(400, "Invalid data")
                elif "GPS" not in data:
                    abort(400, "Invalid data")
                elif "coordinates" not in data["GPS"]:
                    abort(400, "Invalid data")
                elif "timestamp" not in data:
                    abort(400, "Invalid data")
                try:
                    datetime.strptime(data["timestamp"], "%d/%m/%Y %I:%M:%S %p").astimezone(TZ)
                except ValueError:
                    abort(400, "Invalid data")

                handle_blob_created_event(data, blob_url, logger)

        return "OK"
    else:
        abort(400, "Invalid request")
