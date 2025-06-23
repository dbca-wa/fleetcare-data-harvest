import json
from datetime import datetime
from zoneinfo import ZoneInfo

from flask import Blueprint, abort, request
from sqlalchemy.sql import text

from .database import create_device, create_loggedpoint, db, get_device, update_device_details, update_device_registration
from .utils import configure_logging, get_blob_client

bp = Blueprint("fleetcare-data-harvest", __name__)
LOGGER = configure_logging()
TZ = ZoneInfo("Australia/Perth")


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
                # NOTE: we prepend deviceid with `fc_` to avoid unique ID collision with other source types.
                deviceid = f"fc_{data['vehicleID']}"
                registration = data["vehicleRego"]
                coords = data["GPS"]["coordinates"]
                point_wkt = f"POINT({coords[0]} {coords[1]})"
                heading = float(data["readings"]["vehicleHeading"]) if data["readings"]["vehicleHeading"] else 0
                velocity = float(data["readings"]["vehicleSpeed"]) if data["readings"]["vehicleSpeed"] else 0
                altitude = float(data["readings"]["vehicleAltitude"]) if data["readings"]["vehicleAltitude"] else 0
                seen = datetime.strptime(data["timestamp"], "%d/%m/%Y %I:%M:%S %p").astimezone(TZ)
                now_awst = datetime.now().astimezone(TZ)

                # Check whether this device already exists in the database.
                device = get_device(deviceid)

                # If it already exists, update its details.
                if device:
                    id = device[0]  # NOTE: `id` (the table PK) is a different value from `deviceid`.
                    device_last_seen = device[1]
                    current_rego = device[2]

                    # If the device registration differs from Fleetcare data, assume that the tracking device
                    # has been moved between vehicles and update the registration value in Resource Tracking.
                    if registration != current_rego:
                        update_device_registration(id, registration)
                        LOGGER.info(f"Updated device {id} registration to {registration}")

                    # Only update device data if the tracking point was newer than the current device data,
                    # and the tracking point timestamp is no later than "now" in AWST.
                    # Tracking devices sometimes move outside the AWST boundaries, and thus may appear to be
                    # multiple hours into the future. We still preserve the tracking data, but we won't
                    # update the device "last seen" field in this circumstance.
                    if seen > device_last_seen and seen <= now_awst:
                        update_device_details(id, seen, point_wkt, velocity, altitude, heading)
                        LOGGER.info(f"Updated device {id} ({registration}) last seen to {seen}")
                else:  # Create a new device.
                    create_device(deviceid, registration, seen, point_wkt, heading, velocity, altitude)
                    LOGGER.info(f"Created device {deviceid}: {registration}, {seen}")

                    device = get_device(deviceid)
                    id = device[0]

                # Insert new loggedpoint record.
                create_loggedpoint(point_wkt, heading, velocity, altitude, seen, id, blob_url)
                LOGGER.info(f"Logged point for device {id}: {registration}, {seen}")

        db.session.commit()
        return "OK"
    else:
        abort(400, "Invalid request")
