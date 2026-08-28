import random
from datetime import datetime

from windx_tracking.des import Simulation
from windx_tracking.models import Shipment, TrackingEvent
from windx_tracking.route import DEFAULT_ROUTE
from windx_tracking.transport import start_transport


def _run_single_transport(seed: int = 1) -> list[TrackingEvent]:
    sim = Simulation()
    rng = random.Random(seed)
    events: list[TrackingEvent] = []
    shipment = Shipment(shipment_id="SHP-0001", blade_serials=["BLD-A", "BLD-B", "BLD-C"])

    start_transport(sim, shipment, DEFAULT_ROUTE, rng, datetime(2026, 1, 1), 0, events.append)
    sim.run()
    return events


def test_single_transport_produces_expected_event_sequence():
    events = _run_single_transport()

    event_types = [e.event_type for e in events]
    assert event_types == [
        "PICKUP",
        "DEPARTURE",
        "ARRIVAL",
        "DEPARTURE",
        "ARRIVAL",
        "DEPARTURE",
        "ARRIVAL",
        "DEPARTURE",
        "ARRIVAL",
        "LOADED_ON_VESSEL",
    ]


def test_events_have_monotonically_increasing_timestamps():
    events = _run_single_transport()
    timestamps = [e.timestamp for e in events]
    assert timestamps == sorted(timestamps)
    assert len(set(timestamps)) == len(timestamps)


def test_sequence_numbers_are_consecutive_per_shipment():
    events = _run_single_transport()
    assert [e.sequence for e in events] == list(range(1, len(events) + 1))


def test_multiple_transports_are_staggered_and_independent():
    sim = Simulation()
    rng = random.Random(7)
    events: list[TrackingEvent] = []

    for i in range(3):
        shipment = Shipment(shipment_id=f"SHP-{i:04d}", blade_serials=[f"BLD-{i}"])
        start_transport(sim, shipment, DEFAULT_ROUTE, rng, datetime(2026, 1, 1), i * 60, events.append)

    sim.run()

    shipment_ids = {e.shipment.shipment_id for e in events}
    assert shipment_ids == {"SHP-0000", "SHP-0001", "SHP-0002"}
    for shipment_id in shipment_ids:
        per_shipment = [e for e in events if e.shipment.shipment_id == shipment_id]
        assert per_shipment[0].event_type == "PICKUP"
        assert per_shipment[-1].event_type == "LOADED_ON_VESSEL"
