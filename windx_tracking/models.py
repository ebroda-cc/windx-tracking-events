"""Domaenenmodell: Sendung (Shipment) und Tracking-Event."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from .route import Station


@dataclass(frozen=True)
class Shipment:
    shipment_id: str
    # Seriennummern der transportierten Rotorblaetter (i.d.R. 3 pro Transport)
    blade_serials: list[str] = field(default_factory=list)
    carrier: str = "Schwertransport Nord GmbH"
    mode_of_transport: str = "ROAD"


@dataclass(frozen=True)
class TrackingEvent:
    event_id: str
    shipment: Shipment
    # fortlaufende Nummer innerhalb des Transports (1, 2, 3, ...)
    sequence: int
    # PICKUP, ARRIVAL, DEPARTURE oder LOADED_ON_VESSEL
    event_type: str
    # GS1-CBV bizStep-Suffix, z.B. "shipping"
    business_step: str
    # GS1-CBV disposition-Suffix, z.B. "in_transit"
    disposition: str
    station: Station
    timestamp: datetime
    remarks: str = ""

    @property
    def file_stem(self) -> str:
        return f"{self.shipment.shipment_id}_{self.sequence:02d}_{self.event_type}"
