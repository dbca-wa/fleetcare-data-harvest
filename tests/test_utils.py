import json
import os
import random
import string
from datetime import datetime, timedelta

from fleetcare_data_harvest.utils import handle_blob_created_event

with open(os.path.join(os.path.dirname(__file__), "data.json"), "rb") as f:
    _data = json.loads(f.read())
    _data["vehicleID"] = str(random.randint(1000000, 9999999))
    now = datetime.now()
    _data["timestamp"] = now.strftime("%d/%m/%Y %I:%M:%S %p")


def test_blob_created_event():
    assert handle_blob_created_event(_data)


def test_blob_created_event_new_device():
    _data["vehicleID"] = str(random.randint(1000000, 9999999))
    assert handle_blob_created_event(_data)


def test_blob_created_event_new_rego():
    then = datetime.now() - timedelta(minutes=2)
    _data["timestamp"] = then.strftime("%d/%m/%Y %I:%M:%S %p")
    assert handle_blob_created_event(_data)

    _data["vehicleRego"] = f"1{"".join(random.choices(string.ascii_uppercase, k=6))}"
    then = datetime.now() - timedelta(minutes=1)
    _data["timestamp"] = then.strftime("%d/%m/%Y %I:%M:%S %p")

    assert handle_blob_created_event(_data)
