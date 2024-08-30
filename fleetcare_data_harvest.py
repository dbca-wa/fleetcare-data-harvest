#!/usr/bin/python
from bottle import Bottle, request
from datetime import datetime
import json
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.sql import text
from zoneinfo import ZoneInfo

from utils import configure_logging, get_blob_client


dot_env = os.path.join(os.getcwd(), ".env")
if os.path.exists(dot_env):
    from dotenv import load_dotenv

    load_dotenv()

application = Bottle()
TZ = ZoneInfo("Australia/Perth")

# Configure logging.
LOGGER = configure_logging()

# Database connection - create a DB engine and a scoped session for queries.
# https://docs.sqlalchemy.org/en/20/orm/contextual.html#unitofwork-contextual
db_engine = create_engine(os.getenv("DATABASE_URL"))
SESSION = scoped_session(sessionmaker(bind=db_engine, autoflush=True))()


@application.route("/livez")
def liveness():
    return "OK"


@application.route("/readyz")
def readiness():
    result = SESSION.execute(text("SELECT 1")).fetchone()

    if result:
        return "OK"


@application.route("/", method="POST")
def handle_post():
    """Webhook endpoint to receive events for an Azure Event Grid subscription, being creation of new blobs
    containing device tracking data. The endpoint handles both event subscription (required on creation or
    update of subscriptions) and BlobCreated events.
    """
    if request.json:
        for event in request.json:
            # Handle initial event subscription validation.
            # https://learn.microsoft.com/en-us/azure/event-grid/webhook-event-delivery#validation-details.
            if "data" in event and "validationCode" in event["data"]:
                validation_code = event["data"]["validationCode"]
                return {"validationResponse": validation_code}

            # Handle BlobCreated events.
            elif (
                "eventType" in event
                and event["eventType"] == "Microsoft.Storage.BlobCreated"
            ):
                blob_url = event["data"]["url"]
                blob_client = get_blob_client(blob_url)
                blob_content = blob_client.download_blob().read()
                data = json.loads(blob_content)

                source_device_type = "fleetcare"
                deviceid = data["vehicleID"]
                rego = data["vehicleRego"]
                coords = data["GPS"]["coordinates"]
                point = f"SRID=4326;POINT({coords[0]} {coords[1]})"
                heading = (
                    float(data["readings"]["vehicleHeading"])
                    if data["readings"]["vehicleHeading"]
                    else 0
                )
                velocity = (
                    float(data["readings"]["vehicleSpeed"])
                    if data["readings"]["vehicleSpeed"]
                    else 0
                )
                altitude = (
                    float(data["readings"]["vehicleAltitude"])
                    if data["readings"]["vehicleAltitude"]
                    else 0
                )
                timestamp = datetime.strptime(
                    data["timestamp"], "%d/%m/%Y %I:%M:%S %p"
                ).astimezone(TZ)
                seen = timestamp.strftime("%Y-%m-%d %H:%M:%S+8")
                message = 3

                device_sql = text(
                    f"SELECT id, seen FROM tracking_device WHERE source_device_type = '{source_device_type}' AND deviceid LIKE '%{deviceid}'"
                )
                device = SESSION.execute(device_sql).fetchone()

                # NOTE: Tracking points may be delivered out of order.
                if device:
                    device_id = device[0]
                    device_seen = device[1]

                    # Only update device data if the tracking point was newer than the current device data.
                    if timestamp > device_seen:
                        # Update existing device details.
                        device_sql = text(
                            f"""UPDATE tracking_device
                            SET seen = '{seen}'::timestamptz,
                                point = '{point}'::geometry,
                                velocity = {velocity},
                                altitude = {altitude},
                                heading = {heading}
                            WHERE id = {device_id}
                            """
                        )
                        SESSION.execute(device_sql)
                        LOGGER.info(f"Updated device ID {device_id}: {rego}, {seen}")
                else:  # Create a new device.
                    new_device_sql = text(
                        f"""INSERT INTO tracking_device (
                            deviceid,
                            registration,
                            symbol,
                            district,
                            district_display,
                            internal_only,
                            hidden,
                            deleted,
                            seen,
                            point,
                            heading,
                            velocity,
                            altitude,
                            message,
                            source_device_type
                        ) VALUES (
                            'fc_{deviceid}',
                            '{rego}',
                            'other',
                            'OTH',
                            'Other',
                            False,
                            False,
                            False,
                            '{seen}'::timestamptz,
                            '{point}'::geometry,
                            {heading},
                            {velocity},
                            {altitude},
                            3,
                            '{source_device_type}'
                        )"""
                    )
                    SESSION.execute(new_device_sql)
                    LOGGER.info(f"Created device fc_{deviceid}: {rego}, {seen}")
                    device = SESSION.execute(device_sql).fetchone()
                    device_id = device[0]

                # Insert new loggedpoint record.
                loggedpoint_sql = text(
                    f"""INSERT INTO tracking_loggedpoint (
                        point,
                        heading,
                        velocity,
                        altitude,
                        seen,
                        device_id,
                        message,
                        source_device_type,
                        raw
                    )
                    VALUES (
                        '{point}'::geometry,
                        {heading},
                        {velocity},
                        {altitude},
                        '{seen}'::timestamptz,
                        {device_id},
                        {message},
                        '{source_device_type}',
                        '{blob_url}'
                    )"""
                )
                SESSION.execute(loggedpoint_sql)
                LOGGER.info(f"Logged point for device ID {device_id}: {rego}, {seen}")
                SESSION.commit()

    return "OK"


if __name__ == "__main__":
    from bottle import run

    run(
        application,
        host="0.0.0.0",
        port=os.getenv("PORT", 8080),
        reloader=True,
    )
