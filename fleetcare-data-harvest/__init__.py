import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo

from quart import Quart, g, request
from quart_db import QuartDB

from .utils import configure_logging, get_blob_client

dot_env = os.path.join(os.getcwd(), ".env")
if os.path.exists(dot_env):
    from dotenv import load_dotenv

    load_dotenv()

TZ = ZoneInfo("Australia/Perth")
LOGGER = configure_logging()


def create_app(app_config=None):
    """The application factory, used to generate the Quart app instance."""
    app = Quart(__name__)
    database_url = os.getenv("DATABASE_URL", "sqlite:///:memory:")
    app.config["DATABASE_URL"] = database_url

    if app_config:
        app.config.update(app_config)

    db = QuartDB(app, url=database_url)
    db.init_app(app)

    @app.get("/livez")
    async def liveness():
        return "OK"

    @app.get("/readyz")
    async def readiness():
        result = await g.connection.fetch_one("SELECT 1")
        if result:
            return "OK"

    @app.post("/")
    async def handle_blobcreated():
        """Webhook endpoint to receive events for an Azure Event Grid subscription, being creation of new blobs
        containing device tracking data. The endpoint handles both event subscription (required on creation or
        update of subscriptions) and BlobCreated events.
        """
        if request.is_json:
            data = await request.get_json()
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

                    deviceid = data["vehicleID"]
                    deviceid = f"fc_{deviceid}"
                    registration = data["vehicleRego"]
                    coords = data["GPS"]["coordinates"]
                    point = f"SRID=4326;POINT({coords[0]} {coords[1]})"
                    heading = float(data["readings"]["vehicleHeading"]) if data["readings"]["vehicleHeading"] else 0
                    velocity = float(data["readings"]["vehicleSpeed"]) if data["readings"]["vehicleSpeed"] else 0
                    altitude = float(data["readings"]["vehicleAltitude"]) if data["readings"]["vehicleAltitude"] else 0
                    seen = datetime.strptime(data["timestamp"], "%d/%m/%Y %I:%M:%S %p").astimezone(TZ)
                    # timestamp = datetime.strptime(data["timestamp"], "%d/%m/%Y %I:%M:%S %p").astimezone(TZ)
                    # seen = timestamp.strftime("%Y-%m-%d %H:%M:%S+8")
                    now_awst = datetime.now().astimezone(TZ)
                    message = 3
                    source_device_type = "fleetcare"

                    device = await g.connection.fetch_one(
                        "SELECT id, seen, registration FROM tracking_device WHERE source_device_type = :source_device_type AND deviceid = :deviceid",
                        {"source_device_type": source_device_type, "deviceid": deviceid},
                    )

                    if device:
                        id = device["id"]
                        device_last_seen = device["seen"]
                        current_rego = device["registration"]

                        # If the device registration differs from Fleetcare data, assume that the tracking device
                        # has been moved between vehicles and update the registration value in Resource Tracking.
                        if registration != current_rego:
                            await g.connection.execute(
                                "UPDATE tracking_device SET registration = :registration WHERE id = :id",
                                {"registration": registration, "id": id},
                            )
                            LOGGER.info(f"Updated device {id} registration to {registration}")

                        # Only update device data if the tracking point was newer than the current device data,
                        # and the tracking point timestamp is no later than "now" in AWST.
                        # Tracking devices sometimes move outside the AWST boundaries, and thus may appear to be
                        # multiple hours into the future. We still preserve the tracking data, but we won't
                        # update the device "last seen" field in this circumstance.
                        if seen > device_last_seen and seen <= now_awst:
                            # Update existing device details.
                            await g.connection.execute(
                                """UPDATE tracking_device
                            SET seen = :seen::timestamptz,
                                point = :point::geometry,
                                velocity = :velocity,
                                altitude = :altitude,
                                heading = :heading
                            WHERE id = :id""",
                                {"seen": seen, "point": point, "velocity": velocity, "altitude": altitude, "heading": heading, "id": id},
                            )
                            LOGGER.info(f"Updated device {id} ({registration}) last seen to {seen}")
                    else:  # Create a new device.
                        await g.connection.execute(
                            """INSERT INTO tracking_device (
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
                                :deviceid,
                                :registration,
                                :symbol,
                                :district,
                                :district_display,
                                :internal_only,
                                :hidden,
                                :deleted,
                                :seen::timestamptz,
                                :point::geometry,
                                :heading,
                                :velocity,
                                :altitude,
                                :message,
                                :source_device_type
                            )""",
                            {
                                "deviceid": deviceid,
                                "registration": registration,
                                "symbol": "other",
                                "district": "OTH",
                                "district_display": "Other",
                                "internal_only": False,
                                "hidden": False,
                                "deleted": False,
                                "seen": seen,
                                "point": point,
                                "heading": heading,
                                "velocity": velocity,
                                "altitude": altitude,
                                "message": message,
                                "source_device_type": source_device_type,
                            },
                        )
                        LOGGER.info(f"Created device fc_{deviceid}: {registration}, {seen}")
                        device = await g.connection.fetch_one(
                            "SELECT id, seen, registration FROM tracking_device WHERE source_device_type = :source_device_type AND deviceid = :deviceid",
                            {"source_device_type": source_device_type, "deviceid": deviceid},
                        )
                        id = device["id"]

                    # Insert new loggedpoint record.
                    await g.connection.execute(
                        """INSERT INTO tracking_loggedpoint (
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
                            :point::geometry,
                            :heading,
                            :velocity,
                            :altitude,
                            :seen::timestamptz,
                            :id,
                            :message,
                            :source_device_type,
                            :blob_url
                        )""",
                        {
                            "point": point,
                            "heading": heading,
                            "velocity": velocity,
                            "altitude": altitude,
                            "seen": seen,
                            "id": id,
                            "message": message,
                            "source_device_type": source_device_type,
                            "blob_url": blob_url,
                        },
                    )
                    LOGGER.info(f"Logged point for device {id}: {registration}, {seen}")

        return "OK"

    return app
