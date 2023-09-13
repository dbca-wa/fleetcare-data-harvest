import azure.functions as func
from datetime import datetime, timedelta
import json
import os
from pytz import timezone, utc
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
        device_sql = text(f"SELECT id FROM tracking_device WHERE source_device_type = '{source_device_type}' AND deviceid LIKE '%{deviceid}'")
        device = conn.execute(device_sql).fetchone()

        if device:  # Only update reading and insert a loggedpoint if we matched a deviceid.
            coords = data["GPS"]["coordinates"]
            point = f"SRID=4326;POINT({coords[0]} {coords[1]})"
            heading = float(data["readings"]["vehicleHeading"]) if data["readings"]["vehicleHeading"] else 0
            velocity = float(data["readings"]["vehicleSpeed"]) if data["readings"]["vehicleSpeed"] else 0
            altitude = float(data["readings"]["vehicleAltitude"]) if data["readings"]["vehicleAltitude"] else 0
            # Convert the timestamp to UTC.
            timestamp = timestamp.astimezone(utc)
            seen = timestamp.strftime("%Y-%m-%d %H:%M:%S")
            device_id = device[0]
            message = 3

            # Update device details
            device_sql = text(
                f"""UPDATE tracking_device
                SET seen = '{seen}'::timestamp with time zone,
                    point = '{point}'::geometry,
                    velocity = {velocity},
                    altitude = {altitude},
                    heading = {heading}
                WHERE id = {device_id}
                """
            )

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
                    '{seen}'::timestamp with time zone,
                    {device_id},
                    {message},
                    '{source_device_type}',
                    '{blob.name}'
                )"""
            )
            conn.execute(loggedpoint_sql)
            conn.commit()

        conn.close()