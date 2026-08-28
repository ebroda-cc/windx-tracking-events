from datetime import datetime

from windx_tracking.formatters.edi import event_to_edifact
from windx_tracking.formatters.epcis import event_to_epcis, events_to_epcis_document
from windx_tracking.models import Shipment, TrackingEvent
from windx_tracking.route import PORT_GATE


def _make_event(event_type: str = "ARRIVAL", sequence: int = 1) -> TrackingEvent:
    shipment = Shipment(shipment_id="SHP-0001", blade_serials=["BLD-0001-A", "BLD-0001-B"])
    return TrackingEvent(
        event_id="evt-123",
        shipment=shipment,
        sequence=sequence,
        event_type=event_type,
        business_step="receiving",
        disposition="in_progress",
        station=PORT_GATE,
        timestamp=datetime(2026, 3, 1, 14, 30),
        remarks="Ankunft am Hafenterminal (Gate-In)",
    )


def test_edifact_contains_expected_segments():
    event = _make_event()
    text = event_to_edifact(event, interchange_ref=1, message_ref=1)

    assert text.startswith("UNB+UNOC:3+WINDXPLANT:ZZ+PORTAUTH:ZZ+260301:1430+1'")
    assert "BGM+23+SHP-0001+9'" in text
    assert "IFTSTA:D:96A:UN:EAN008" in text
    assert "GIN+BJ+BLD-0001-A'" in text
    assert "GIN+BJ+BLD-0001-B'" in text
    assert f"LOC+147+{PORT_GATE.un_locode}'" in text
    assert "STS+1+ARRI+receiving'" in text
    assert text.strip().endswith("UNZ+1+1'")


def test_edifact_unt_segment_count_matches_body():
    event = _make_event()
    text = event_to_edifact(event, interchange_ref=1, message_ref=1)
    lines = [line for line in text.strip().split("\n")]

    unh_index = next(i for i, line in enumerate(lines) if line.startswith("UNH"))
    unt_index = next(i for i, line in enumerate(lines) if line.startswith("UNT"))
    expected_count = unt_index - unh_index + 1

    unt_declared_count = int(lines[unt_index].split("+")[1])
    assert unt_declared_count == expected_count


def test_epcis_object_event_structure():
    event = _make_event()
    doc = event_to_epcis(event)

    assert doc["type"] == "EPCISDocument"
    events = doc["epcisBody"]["eventList"]
    assert len(events) == 1
    obj_event = events[0]

    assert obj_event["type"] == "ObjectEvent"
    assert obj_event["action"] == "OBSERVE"
    assert obj_event["bizStep"] == "urn:epcglobal:cbv:bizstep:receiving"
    assert obj_event["disposition"] == "urn:epcglobal:cbv:disp:in_progress"
    assert obj_event["eventTime"] == "2026-03-01T14:30:00"
    assert len(obj_event["epcList"]) == 2
    assert obj_event["epcList"][0].startswith("urn:epc:id:sgtin:")
    assert obj_event["readPoint"]["id"] == obj_event["bizLocation"]["id"]
    assert obj_event["windx:shipmentId"] == "SHP-0001"
    assert obj_event["windx:eventType"] == "ARRIVAL"


def test_events_to_epcis_document_sorts_chronologically():
    early = _make_event(event_type="ARRIVAL", sequence=1)
    late_shipment = Shipment(shipment_id="SHP-0001", blade_serials=["BLD-0001-A"])
    late = TrackingEvent(
        event_id="evt-456",
        shipment=late_shipment,
        sequence=2,
        event_type="DEPARTURE",
        business_step="transporting",
        disposition="in_transit",
        station=PORT_GATE,
        timestamp=datetime(2026, 3, 1, 15, 0),
        remarks="",
    )

    doc = events_to_epcis_document([late, early])
    event_ids = [e["eventID"] for e in doc["epcisBody"]["eventList"]]
    assert event_ids == ["evt-123", "evt-456"]
