"""EDI-Darstellung eines Tracking-Events als vereinfachte UN/EDIFACT
IFTSTA-Nachricht (International Multimodal Status Report) -- der
Standardnachrichtentyp fuer Transport-Statusmeldungen.

Hinweis: Zur besseren Lesbarkeit wird nach jedem Segment ein Zeilenumbruch
eingefuegt; im realen EDIFACT-Interchange entfaellt dieser. Ebenso ist die
Codeliste in ``STATUS_CODES`` eine vereinfachte, illustrative Auswahl und
kein vollstaendiger UN/EDIFACT-4079-Codesatz.
"""

from __future__ import annotations

from datetime import datetime

from ..models import TrackingEvent

SEGMENT_TERMINATOR = "'"

STATUS_CODES = {
    "PICKUP": "PICK",
    "ARRIVAL": "ARRI",
    "DEPARTURE": "DEPA",
    "LOADED_ON_VESSEL": "LOAD",
}


def _fmt_unb_datetime(dt: datetime) -> str:
    return dt.strftime("%y%m%d:%H%M")


def _fmt_dtm_datetime(dt: datetime) -> str:
    return dt.strftime("%Y%m%d%H%M")


def event_to_edifact(
    event: TrackingEvent,
    interchange_ref: int,
    message_ref: int,
    sender: str = "WINDXPLANT",
    receiver: str = "PORTAUTH",
) -> str:
    """Erzeugt eine vereinfachte IFTSTA-Nachricht fuer ``event``."""

    station = event.station
    shipment = event.shipment

    header = (
        f"UNB+UNOC:3+{sender}:ZZ+{receiver}:ZZ+"
        f"{_fmt_unb_datetime(event.timestamp)}+{interchange_ref}"
    )

    body = [
        f"UNH+{message_ref}+IFTSTA:D:96A:UN:EAN008",
        f"BGM+23+{shipment.shipment_id}+9",
        f"DTM+137:{_fmt_dtm_datetime(event.timestamp)}:203",
        f"NAD+CA+++{shipment.carrier}",
        f"TDT+20+{shipment.mode_of_transport}",
        *[f"GIN+BJ+{serial}" for serial in shipment.blade_serials],
        f"LOC+147+{station.un_locode}",
        f"FTX+ZZZ+++{station.name}",
        f"STS+1+{STATUS_CODES[event.event_type]}+{event.business_step}",
        f"DTM+334:{_fmt_dtm_datetime(event.timestamp)}:203",
        f"FTX+AAI+++{event.remarks}",
        f"RFF+ACW:{event.event_id}",
    ]
    unt = f"UNT+{len(body) + 1}+{message_ref}"
    footer = f"UNZ+1+{interchange_ref}"

    lines = [header, *body, unt, footer]
    return "\n".join(f"{line}{SEGMENT_TERMINATOR}" for line in lines) + "\n"
