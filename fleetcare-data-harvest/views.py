import json

from flask import Blueprint, abort, request
from sqlalchemy.sql import text

from .database import db
from .utils import configure_logging, get_blob_client, handle_blob_created_event

bp = Blueprint("fleetcare-data-harvest", __name__)
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
                blob_url = event["data"]["url"]
                blob_client = get_blob_client(blob_url)
                blob_content = blob_client.download_blob().read()
                data = json.loads(blob_content)
                handle_blob_created_event(data, blob_url, logger)

        return "OK"
    else:
        abort(400, "Invalid request")
