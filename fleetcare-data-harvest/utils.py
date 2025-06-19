import logging
import os
import sys

from azure.storage.blob import BlobClient


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
