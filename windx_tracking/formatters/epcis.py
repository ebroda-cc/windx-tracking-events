"""EPCIS-Darstellung eines Tracking-Events als GS1 EPCIS 2.0 ObjectEvent
(JSON-LD).

Hinweis: EPC- und SGLN-Kennungen basieren auf einem fiktiven
Firmenpraefix ("4012345") und dienen der Veranschaulichung -- sie sind
keine real registrierten GS1-Schluessel. ``bizStep``/``disposition``
nutzen echte GS1-CBV-Vokabular-Suffixe (siehe
https://ref.gs1.org/cbv/), die Zuordnung der einzelnen Stationsereignisse
darauf ist jedoch eine vereinfachte, fuer diese Simulation getroffene
Wahl.
"""

from __future__ import annotations

from ..models import TrackingEvent

CBV_BIZSTEP_BASE = "urn:epcglobal:cbv:bizstep:"
CBV_DISPOSITION_BASE = "urn:epcglobal:cbv:disp:"

WINDX_NAMESPACE = "https://example.org/windx-tracking#"


def _epc(serial: str) -> str:
    """Fiktive SGTIN-EPC-URN fuer ein Rotorblatt anhand seiner Seriennummer."""
    return f"urn:epc:id:sgtin:4012345.012345.{serial}"


def _sgln(station_gln: str) -> str:
    return f"urn:epc:id:sgln:{station_gln}.0"


def _object_event(event: TrackingEvent) -> dict:
    station = event.station
    shipment = event.shipment
    location = _sgln(station.gln)

    return {
        "type": "ObjectEvent",
        "eventID": event.event_id,
        "eventTime": event.timestamp.isoformat(),
        "eventTimeZoneOffset": "+00:00",
        "epcList": [_epc(serial) for serial in shipment.blade_serials],
        "action": "OBSERVE",
        "bizStep": f"{CBV_BIZSTEP_BASE}{event.business_step}",
        "disposition": f"{CBV_DISPOSITION_BASE}{event.disposition}",
        "readPoint": {"id": location},
        "bizLocation": {"id": location},
        "windx:shipmentId": shipment.shipment_id,
        "windx:carrier": shipment.carrier,
        "windx:stationType": station.station_type,
        "windx:stationName": station.name,
        "windx:eventType": event.event_type,
        "windx:sequence": event.sequence,
        "windx:remarks": event.remarks,
    }


def _epcis_document(events: list[dict]) -> dict:
    return {
        "@context": [
            "https://ref.gs1.org/standards/epcis/2.0.0/epcis-context.jsonld",
            {"windx": WINDX_NAMESPACE},
        ],
        "type": "EPCISDocument",
        "schemaVersion": "2.0",
        "creationDate": events[0]["eventTime"] if events else None,
        "epcisBody": {"eventList": events},
    }


def event_to_epcis(event: TrackingEvent) -> dict:
    """Einzelnes Event als vollstaendiges EPCISDocument (ein Event)."""
    return _epcis_document([_object_event(event)])


def events_to_epcis_document(events: list[TrackingEvent]) -> dict:
    """Mehrere Events (z.B. eines ganzen Laufs) in einem EPCISDocument,
    chronologisch sortiert."""
    ordered = sorted(events, key=lambda e: e.timestamp)
    return _epcis_document([_object_event(e) for e in ordered])
