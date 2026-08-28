"""Transport-Prozess: fuehrt eine Sendung entlang der Route und erzeugt an
jeder Station die passenden Tracking-Events.

Jede Station erzeugt (bis auf Sonderfaelle am Anfang/Ende) genau zwei
Events: ein Ankunfts- und ein Abfahrtsereignis, mit einer dazwischen
liegenden, zufaellig gezogenen Verweildauer (Kontrolle, Ruhezeit,
Zwischenlagerung, ...). Die Fahrzeiten zwischen Stationen werden aus
Distanz und Durchschnittsgeschwindigkeit der jeweiligen Teilstrecke mit
etwas Zufallsstreuung abgeleitet.
"""

from __future__ import annotations

import itertools
import random
import uuid
from datetime import datetime, timedelta
from typing import Callable, Iterator

from .models import Shipment, TrackingEvent
from .route import Route, RouteLeg, Station

OnEvent = Callable[[TrackingEvent], None]

# (station_type, phase) -> (event_type, business_step, disposition, remarks)
# business_step/disposition sind vereinfachte, aber an die GS1-CBV
# angelehnte Suffixe (siehe formatters/epcis.py).
EVENT_DEFINITIONS: dict[tuple[str, str], tuple[str, str, str, str]] = {
    ("FACTORY", "depart"): (
        "DEPARTURE", "shipping", "in_transit",
        "Abfahrt vom Werk nach Verladung auf den Schwerlast-Trailer",
    ),
    ("CHECKPOINT", "arrive"): (
        "ARRIVAL", "inspecting", "in_progress",
        "Ankunft an Kontrollstelle fuer Gross- und Schwertransporte",
    ),
    ("CHECKPOINT", "depart"): (
        "DEPARTURE", "transporting", "in_transit",
        "Kontrolle abgeschlossen, Weiterfahrt",
    ),
    ("HUB", "arrive"): (
        "ARRIVAL", "storing", "in_progress",
        "Ankunft am Nachtlager (gesetzliches Nachtfahrverbot fuer Schwertransporte)",
    ),
    ("HUB", "depart"): (
        "DEPARTURE", "transporting", "in_transit",
        "Ruhezeit beendet, Weiterfahrt Richtung Hafen",
    ),
    ("PORT_GATE", "arrive"): (
        "ARRIVAL", "receiving", "in_progress",
        "Ankunft am Hafenterminal (Gate-In)",
    ),
    ("PORT_GATE", "depart"): (
        "DEPARTURE", "transporting", "in_transit",
        "Gate-In abgeschlossen, Weiterfahrt zur Lagerflaeche",
    ),
    ("PORT_YARD", "arrive"): (
        "ARRIVAL", "unloading", "in_progress",
        "Ankunft auf der Schwerlast-Lagerflaeche, Entladung vom Trailer",
    ),
    ("PORT_YARD", "final"): (
        "LOADED_ON_VESSEL", "loading", "in_transit",
        "Verladung der Rotorblaetter auf das Seeschiff",
    ),
}

PICKUP_DEFINITION: tuple[str, str, str, str] = (
    "PICKUP", "staging_outbound", "staging_outbound",
    "Rotorblaetter zur Verladung auf dem Werksgelaende bereitgestellt",
)


def _sample_travel_minutes(rng: random.Random, leg: RouteLeg) -> float:
    base_hours = leg.distance_km / leg.avg_speed_kmh
    jitter = rng.uniform(1 - leg.speed_variability, 1 + leg.speed_variability)
    return max(base_hours, 0.05) * 60 * jitter


def _sample_dwell_minutes(rng: random.Random, route: Route, station: Station) -> float:
    dwell = route.dwell_times[station.code]
    return rng.triangular(dwell.min_minutes, dwell.max_minutes, dwell.mode_minutes)


def transport_process(
    sim,
    shipment: Shipment,
    route: Route,
    rng: random.Random,
    sim_start: datetime,
    on_event: OnEvent,
) -> Iterator[float]:
    """Generator-Prozess fuer genau einen Transport entlang ``route``.

    Wird per ``sim.process(...)`` bei der :class:`~windx_tracking.des.Simulation`
    eingeplant. ``yield <minuten>`` haelt den Prozess an, bis die
    Simulationszeit entsprechend fortgeschritten ist.
    """

    sequence = itertools.count(1)

    def emit(station: Station, definition: tuple[str, str, str, str]) -> None:
        event_type, business_step, disposition, remarks = definition
        event = TrackingEvent(
            event_id=str(uuid.uuid4()),
            shipment=shipment,
            sequence=next(sequence),
            event_type=event_type,
            business_step=business_step,
            disposition=disposition,
            station=station,
            timestamp=sim_start + timedelta(minutes=sim.now),
            remarks=remarks,
        )
        on_event(event)

    factory = route.stations[0]
    emit(factory, PICKUP_DEFINITION)
    yield _sample_dwell_minutes(rng, route, factory)
    emit(factory, EVENT_DEFINITIONS[(factory.station_type, "depart")])

    for station in route.stations[1:]:
        leg = route.leg_to(station)
        yield _sample_travel_minutes(rng, leg)

        is_last = station is route.stations[-1]
        emit(station, EVENT_DEFINITIONS[(station.station_type, "arrive")])
        yield _sample_dwell_minutes(rng, route, station)

        if is_last:
            emit(station, EVENT_DEFINITIONS[(station.station_type, "final")])
        else:
            emit(station, EVENT_DEFINITIONS[(station.station_type, "depart")])


def start_transport(
    sim,
    shipment: Shipment,
    route: Route,
    rng: random.Random,
    sim_start: datetime,
    start_offset: float,
    on_event: OnEvent,
) -> None:
    """Plant den Start eines Transports zum Zeitpunkt ``start_offset`` ein
    (relativ zur aktuellen Simulationszeit), sodass mehrere Transporte
    zeitversetzt gestartet werden koennen."""

    sim.schedule(
        start_offset,
        lambda: sim.process(transport_process(sim, shipment, route, rng, sim_start, on_event)),
    )
