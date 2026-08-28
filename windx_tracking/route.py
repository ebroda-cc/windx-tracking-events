"""Stationen und Route fuer den Rotorblatt-Transport vom Werk zum Hafen.

Fuer diese erste Version ist die Route fuer alle Transporte identisch
(``DEFAULT_ROUTE``); das Modell erlaubt aber grundsaetzlich beliebige
weitere Routen, falls spaeter unterschiedliche Wege benoetigt werden.

Hinweis: UN/LOCODEs und GLNs der Zwischenstationen (Werk, Kontrollstelle,
Nachtlager) sind zu Demonstrationszwecken frei erfunden. Der Zielhafen
Cuxhaven ist real und wird tatsaechlich fuer den Export von
Windenergieanlagen-Komponenten genutzt; der UN/LOCODE ``DECUX`` ist echt.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Station:
    code: str
    name: str
    # FACTORY, CHECKPOINT, HUB, PORT_GATE oder PORT_YARD
    station_type: str
    country: str = "DE"
    # GLN in der Form "<Firmenpraefix>.<Standortreferenz>" (fiktiv), Basis
    # fuer die EPCIS-SGLN-Kennung (bizLocation/readPoint).
    gln: str = ""
    # UN/LOCODE fuer die EDI-LOC-Segmente.
    un_locode: str = ""


@dataclass(frozen=True)
class RouteLeg:
    origin: Station
    destination: Station
    distance_km: float
    avg_speed_kmh: float
    # relative Schwankung der Fahrzeit (z.B. Verkehr, Wetter, Pausen)
    speed_variability: float = 0.15


@dataclass(frozen=True)
class StationDwell:
    """Verweildauer (in Minuten) an einer Station zwischen Ankunfts- und
    Abfahrts-/Abschlussereignis, als Dreieck-Verteilung (min, max, modus)."""

    min_minutes: float
    max_minutes: float
    mode_minutes: float


@dataclass
class Route:
    name: str
    stations: list[Station]
    legs: list[RouteLeg]
    dwell_times: dict[str, StationDwell]

    def leg_to(self, station: Station) -> RouteLeg:
        for leg in self.legs:
            if leg.destination.code == station.code:
                return leg
        raise KeyError(f"Keine Teilstrecke fuehrt zu Station {station.code!r}")


FACTORY = Station(
    code="STA-FACTORY",
    name="Rotorblattwerk Luenen",
    station_type="FACTORY",
    gln="4012345.00001",
    un_locode="DEXFA",
)
CHECKPOINT = Station(
    code="STA-CHECKPOINT",
    name="Kontrollstelle A2 fuer Gross- und Schwertransporte",
    station_type="CHECKPOINT",
    gln="4012345.00002",
    un_locode="DEXCK",
)
HUB = Station(
    code="STA-HUB",
    name="Nachtlager Rastanlage Dammer Berge",
    station_type="HUB",
    gln="4012345.00003",
    un_locode="DEXHB",
)
PORT_GATE = Station(
    code="STA-PORT-GATE",
    name="Hafen Cuxhaven - Terminalzufahrt (Gate)",
    station_type="PORT_GATE",
    gln="4012345.00004",
    un_locode="DECUX",
)
PORT_YARD = Station(
    code="STA-PORT-YARD",
    name="Hafen Cuxhaven - Schwerlast-Kai 5",
    station_type="PORT_YARD",
    gln="4012345.00005",
    un_locode="DECUX",
)

DEFAULT_ROUTE = Route(
    name="Werk Luenen -> Hafen Cuxhaven (Standardroute)",
    stations=[FACTORY, CHECKPOINT, HUB, PORT_GATE, PORT_YARD],
    legs=[
        RouteLeg(FACTORY, CHECKPOINT, distance_km=85, avg_speed_kmh=45),
        RouteLeg(CHECKPOINT, HUB, distance_km=160, avg_speed_kmh=50),
        RouteLeg(HUB, PORT_GATE, distance_km=140, avg_speed_kmh=50),
        RouteLeg(PORT_GATE, PORT_YARD, distance_km=2, avg_speed_kmh=15),
    ],
    dwell_times={
        # Verladung der Blätter auf den Schwerlast-Trailer
        FACTORY.code: StationDwell(min_minutes=60, max_minutes=150, mode_minutes=90),
        # Kontrolle/Wiegung des Grossraumtransports
        CHECKPOINT.code: StationDwell(min_minutes=15, max_minutes=45, mode_minutes=25),
        # gesetzliches Nachtfahrverbot fuer Schwertransporte -> Uebernachtung
        HUB.code: StationDwell(min_minutes=480, max_minutes=600, mode_minutes=540),
        # Gate-In / Zollformalitaeten am Hafen
        PORT_GATE.code: StationDwell(min_minutes=30, max_minutes=90, mode_minutes=45),
        # Zwischenlagerung auf der Schwerlastflaeche bis zur Schiffsverladung
        PORT_YARD.code: StationDwell(min_minutes=720, max_minutes=2880, mode_minutes=1440),
    },
)
