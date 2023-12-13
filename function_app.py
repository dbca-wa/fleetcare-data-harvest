import azure.functions as func
from datetime import datetime, timedelta
import json
import os
from pytz import timezone
from sqlalchemy import create_engine
from sqlalchemy.sql import text


app = func.FunctionApp()
awst = timezone("Australia/Perth")
# Define DATABASE_URL in environment vars in the format postgresql+psycopg://user:password@hostname/database
database_url = os.environ.get("DATABASE_URL", None)


@app.function_name(name="FleetcareTrackingData")
@app.blob_trigger(arg_name="blob", path="tracking", connection="STORAGE_CONNECTION_STRING")
def main(blob: func.InputStream):
    data = json.loads(blob.read())
    # Reference: https://learn.microsoft.com/en-us/python/api/azure-functions/azure.functions.blob.inputstream

    # Only process blobs having a timestamp newer than BLOB_PROCESS_THRESHOLD (minutes).
    # This is to reduce the incidence of the function trying to process all blobs uploaded since
    # the dawn of time.
    timestamp = datetime.strptime(data["timestamp"], "%d/%m/%Y %I:%M:%S %p").astimezone(awst)
    threshold = int(os.environ.get("BLOB_PROCESS_THRESHOLD", 1440))  # Default to a threshold of one day.
    since = datetime.now().astimezone(awst) - timedelta(minutes=threshold)
    if timestamp < since:
        return

    engine = create_engine(database_url)

    with engine.connect() as conn:
        source_device_type = "fleetcare"
        deviceid = data["vehicleID"]
        rego = data["vehicleRego"]
        coords = data["GPS"]["coordinates"]
        point = f"SRID=4326;POINT({coords[0]} {coords[1]})"
        heading = float(data["readings"]["vehicleHeading"]) if data["readings"]["vehicleHeading"] else 0
        velocity = float(data["readings"]["vehicleSpeed"]) if data["readings"]["vehicleSpeed"] else 0
        altitude = float(data["readings"]["vehicleAltitude"]) if data["readings"]["vehicleAltitude"] else 0
        seen = timestamp.strftime("%Y-%m-%d %H:%M:%S+8")
        message = 3

        device_sql = text(f"SELECT id FROM tracking_device WHERE source_device_type = '{source_device_type}' AND deviceid LIKE '%{deviceid}'")
        device = conn.execute(device_sql).fetchone()

        if device:  # Only update device data if we matched an existing deviceid.
            device_id = device[0]

            # Update device details
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
            conn.execute(device_sql)
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
            conn.execute(new_device_sql)
            conn.commit()
            device = conn.execute(device_sql).fetchone()
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
                '{blob.name}'
            )"""
        )
        conn.execute(loggedpoint_sql)
        conn.commit()
        conn.close()
