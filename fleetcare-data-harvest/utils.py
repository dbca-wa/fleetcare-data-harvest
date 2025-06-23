import logging
import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

from azure.storage.blob import BlobClient

from .database import create_device, create_loggedpoint, db, get_device, update_device_details, update_device_registration

TZ = ZoneInfo("Australia/Perth")


def configure_logging():
    """
    Configure logging (stdout and file) for the default logger and for the `azure` logger.
    """
    formatter = logging.Formatter("{asctime} | {levelname} | {message}", style="{")
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.INFO)
    handler.setFormatter(formatter)

    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)

    # Set the logging level for all azure-* libraries (the azure-storage-blob library uses this one).
    # Reference: https://learn.microsoft.com/en-us/azure/developer/python/sdk/azure-sdk-logging
    azure_logger = logging.getLogger("azure")
    azure_logger.setLevel(logging.WARNING)

    return logger


def get_blob_client(blob_url, conn_str=None, container_name=None):
    """
    Returns a BlobClient from a URL. If the connection strinf and container name aren't
    passed in, assume that they are present as environment variables.

    https://learn.microsoft.com/en-us/python/api/azure-storage-blob/azure.storage.blob.blobclient
    """
    if not conn_str:
        conn_str = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    if not container_name:
        container_name = os.getenv("AZURE_CONTAINER")

    # Instantiate a BlobClient from the connection string to get the credential.
    credential = BlobClient.from_connection_string(conn_str, container_name, "blob").credential

    # Instantiate and return a BlobClient using the credential.
    return BlobClient.from_blob_url(blob_url, credential)


def handle_blob_created_event(data, blob_url, logger=None):
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
            if logger:
                logger.info(f"Updated device {id} registration to {registration}")

        # Only update device data if the tracking point was newer than the current device data,
        # and the tracking point timestamp is no later than "now" in AWST.
        # Tracking devices sometimes move outside the AWST boundaries, and thus may appear to be
        # multiple hours into the future. We still preserve the tracking data, but we won't
        # update the device "last seen" field in this circumstance.
        if seen > device_last_seen and seen <= now_awst:
            update_device_details(id, seen, point_wkt, velocity, altitude, heading)
            if logger:
                logger.info(f"Updated device {id} ({registration}) last seen to {seen}")
    else:  # Create a new device.
        create_device(deviceid, registration, seen, point_wkt, heading, velocity, altitude)
        if logger:
            logger.info(f"Created device {deviceid}: {registration}, {seen}")

        device = get_device(deviceid)
        id = device[0]

    # Insert new loggedpoint record.
    create_loggedpoint(point_wkt, heading, velocity, altitude, seen, id, blob_url)
    if logger:
        logger.info(f"Logged point for device {id}: {registration}, {seen}")

    db.session.commit()

    return device
