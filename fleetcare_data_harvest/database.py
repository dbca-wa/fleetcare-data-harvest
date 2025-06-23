from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.sql import text

db = SQLAlchemy()


def get_device(deviceid, source_device_type="fleetcare"):
    """Query the database for a Fleetcare device by unique `deviceid`."""
    sql = text(
        """SELECT id, seen, registration, deviceid
FROM tracking_device
WHERE deviceid = :deviceid
AND source_device_type = :source_device_type"""
    ).bindparams(
        deviceid=deviceid,
        source_device_type=source_device_type,
    )
    device = db.session.execute(sql).fetchone()
    return device


def update_device_registration(id, registration):
    """Update a tracking device registration value."""
    sql = text(
        """UPDATE tracking_device
SET registration = :registration
WHERE id = :id"""
    ).bindparams(
        id=id,
        registration=registration,
    )
    db.session.execute(sql)
    db.session.commit()
    return True


def update_device_details(id, seen, point_wkt, velocity, altitude, heading):
    """Update tracking device details."""
    sql = text("""UPDATE tracking_device
SET seen = :seen,
    point = ST_SetSRID(ST_GeomFromText(:point_wkt), 4326),
    velocity = :velocity,
    altitude = :altitude,
    heading = :heading
WHERE id = :id""").bindparams(
        id=id,
        seen=seen,
        point_wkt=point_wkt,
        velocity=velocity,
        altitude=altitude,
        heading=heading,
    )
    db.session.execute(sql)
    db.session.commit()
    return True


def create_device(
    deviceid,
    registration,
    seen,
    point_wkt,
    heading,
    velocity,
    altitude,
    symbol="other",
    district="OTH",
    district_display="Other",
    internal_only=False,
    hidden=False,
    deleted=False,
    message=3,
    source_device_type="fleetcare",
):
    """Create a new device record."""
    sql = text("""INSERT INTO tracking_device (
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
    :seen,
    ST_SetSRID(ST_GeomFromText(:point_wkt), 4326),
    :heading,
    :velocity,
    :altitude,
    :message,
    :source_device_type
)""").bindparams(
        deviceid=deviceid,
        registration=registration,
        symbol=symbol,
        district=district,
        district_display=district_display,
        internal_only=internal_only,
        hidden=hidden,
        deleted=deleted,
        seen=seen,
        point_wkt=point_wkt,
        heading=heading,
        velocity=velocity,
        altitude=altitude,
        message=message,
        source_device_type=source_device_type,
    )
    db.session.execute(sql)
    db.session.commit()
    return True


def create_loggedpoint(point_wkt, heading, velocity, altitude, seen, id, blob_url, message=3, source_device_type="fleetcare"):
    """Create a new logged point record."""
    sql = text("""INSERT INTO tracking_loggedpoint (
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
    ST_SetSRID(ST_GeomFromText(:point_wkt), 4326),
    :heading,
    :velocity,
    :altitude,
    :seen,
    :id,
    :message,
    :source_device_type,
    :blob_url
)""").bindparams(
        point_wkt=point_wkt,
        heading=heading,
        velocity=velocity,
        altitude=altitude,
        seen=seen,
        id=id,
        message=message,
        source_device_type=source_device_type,
        blob_url=blob_url,
    )
    db.session.execute(sql)
    db.session.commit()
    return True
