"""Kommandozeilen-Einstiegspunkt: startet mehrere Transporte auf der
Standardroute, simuliert sie ereignisdiskret und gibt die dabei erzeugten
Tracking-Events aus -- optional als EDI- und EPCIS-Dateien.

Beispiele:

    python -m windx_tracking --transports 3
    python -m windx_tracking --transports 5 --interval-minutes 240 --output-dir out

    # AAS-Objekte (Shell je Sendung + Submodel je Event) zusaetzlich lokal
    # als JSON ablegen, ohne einen AAS-Server anzusprechen:
    python -m windx_tracking --transports 2 --aas-output-dir out/aas

    # ... oder direkt auf die (je Location konfigurierten) AAS-Server hochladen:
    python -m windx_tracking --transports 2 --upload-aas \\
        --aas-server-config aas-servers.json

    # ... und die dort liegenden Sendungs-AAS zusaetzlich als Dataspace-Assets
    # ueber die je Location zustaendigen EDC-Connectoren anbieten:
    python -m windx_tracking --transports 2 --upload-aas --offer-edc-assets \\
        --aas-server-config aas-servers.json --edc-connector-config edc-connectors.json
"""

from __future__ import annotations

import argparse
import json
import random
from datetime import datetime
from pathlib import Path

from .aas.pipeline import export_events_as_aas, upload_events_as_aas
from .aas.server import AasServerRegistry
from .des import Simulation
from .edc.pipeline import export_events_as_dataspace_assets, offer_events_as_dataspace_assets
from .edc.server import EdcConnectorRegistry
from .formatters.edi import event_to_edifact
from .formatters.epcis import event_to_epcis, events_to_epcis_document
from .models import Shipment, TrackingEvent
from .route import DEFAULT_ROUTE
from .transport import start_transport


def run(
    num_transports: int,
    seed: int,
    start_time: datetime,
    interval_minutes: float,
) -> list[TrackingEvent]:
    sim = Simulation()
    rng = random.Random(seed)
    events: list[TrackingEvent] = []

    def on_event(event: TrackingEvent) -> None:
        events.append(event)
        print(
            f"[t={sim.now:8.1f} min | {event.timestamp:%Y-%m-%d %H:%M}] "
            f"{event.shipment.shipment_id:<10} {event.event_type:<17} @ {event.station.name}"
        )

    for i in range(num_transports):
        shipment = Shipment(
            shipment_id=f"SHP-{i + 1:04d}",
            blade_serials=[f"BLD-{i + 1:04d}-{suffix}" for suffix in ("A", "B", "C")],
        )
        start_transport(sim, shipment, DEFAULT_ROUTE, rng, start_time, i * interval_minutes, on_event)

    sim.run()
    return events


def write_outputs(events: list[TrackingEvent], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    for idx, event in enumerate(events, start=1):
        edi_text = event_to_edifact(event, interchange_ref=idx, message_ref=idx)
        (output_dir / f"{event.file_stem}.edi").write_text(edi_text, encoding="utf-8")

        epcis_doc = event_to_epcis(event)
        (output_dir / f"{event.file_stem}.epcis.json").write_text(
            json.dumps(epcis_doc, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    combined = events_to_epcis_document(events)
    (output_dir / "all_events.epcis.json").write_text(
        json.dumps(combined, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Ereignisdiskrete Simulation fuer den Transport von Rotorblaettern "
            "vom Produzenten zum Hafen."
        )
    )
    parser.add_argument("--transports", type=int, default=3, help="Anzahl simulierter Transporte")
    parser.add_argument("--seed", type=int, default=42, help="Zufalls-Seed fuer Reproduzierbarkeit")
    parser.add_argument(
        "--start", type=str, default=None, help="Startzeitpunkt (ISO-8601), Default: jetzt"
    )
    parser.add_argument(
        "--interval-minutes",
        type=float,
        default=180.0,
        help="Zeitlicher Abstand zwischen dem Start zweier Transporte (Minuten)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Wenn gesetzt: EDI- und EPCIS-Dateien je Event in diesem Verzeichnis ablegen",
    )
    parser.add_argument(
        "--aas-output-dir",
        type=str,
        default=None,
        help="Wenn gesetzt: AAS-Shell-/Submodel-JSON je Event lokal in diesem Verzeichnis ablegen",
    )
    parser.add_argument(
        "--upload-aas",
        action="store_true",
        help="AAS-Shells/-Submodels zusaetzlich auf die je Station zustaendigen AAS-Server hochladen",
    )
    parser.add_argument(
        "--aas-server-config",
        type=str,
        default=None,
        help=(
            "JSON-Datei mit Station-Code -> AAS-Server-URL (ueberschreibt "
            "Station.aas_server_url je Location), z.B. "
            '\'{"STA-FACTORY": "https://factory.example.com/aas"}\''
        ),
    )
    parser.add_argument(
        "--edc-output-dir",
        type=str,
        default=None,
        help=(
            "Wenn gesetzt: Asset-/Policy-/Contract-Definition-JSON je Location+Sendung "
            "lokal in diesem Verzeichnis ablegen (ohne EDC-Connector anzusprechen)"
        ),
    )
    parser.add_argument(
        "--offer-edc-assets",
        action="store_true",
        help=(
            "Fuer jede Sendung an jeder durchlaufenen Location ein Dataspace-Asset "
            "(inkl. Policy- und Contract-Definition) im dortigen EDC-Connector anlegen"
        ),
    )
    parser.add_argument(
        "--edc-connector-config",
        type=str,
        default=None,
        help=(
            "JSON-Datei mit Station-Code -> EDC-Management-API-URL (oder "
            '{"management_url": ..., "api_key": ...}), ueberschreibt '
            "Station.edc_management_url je Location"
        ),
    )
    args = parser.parse_args()

    start_time = datetime.fromisoformat(args.start) if args.start else datetime.now()
    events = run(args.transports, args.seed, start_time, args.interval_minutes)

    print(f"\n{len(events)} Events fuer {args.transports} Transport(e) erzeugt.")

    if args.output_dir:
        output_dir = Path(args.output_dir)
        write_outputs(events, output_dir)
        print(f"EDI- und EPCIS-Dateien geschrieben nach: {output_dir.resolve()}")

    if args.aas_output_dir:
        aas_output_dir = Path(args.aas_output_dir)
        export_events_as_aas(events, aas_output_dir)
        print(f"AAS-Shell-/Submodel-JSON geschrieben nach: {aas_output_dir.resolve()}")

    needs_aas_registry = args.upload_aas or args.offer_edc_assets or args.edc_output_dir
    aas_registry = None
    if needs_aas_registry:
        aas_registry = (
            AasServerRegistry.from_json_file(args.aas_server_config)
            if args.aas_server_config
            else AasServerRegistry()
        )

    if args.upload_aas:
        upload_events_as_aas(events, aas_registry)
        print(f"{len(events)} Events als AAS auf die konfigurierten Server hochgeladen.")

    if args.edc_output_dir:
        edc_output_dir = Path(args.edc_output_dir)
        export_events_as_dataspace_assets(events, aas_registry, edc_output_dir)
        print(f"Dataspace-Asset-/Policy-/Contract-Definition-JSON geschrieben nach: {edc_output_dir.resolve()}")

    if args.offer_edc_assets:
        edc_registry = (
            EdcConnectorRegistry.from_json_file(args.edc_connector_config)
            if args.edc_connector_config
            else EdcConnectorRegistry()
        )
        offer_events_as_dataspace_assets(events, edc_registry, aas_registry)
        print(f"Dataspace-Assets fuer {len(events)} Events an den konfigurierten EDC-Connectoren angelegt.")


if __name__ == "__main__":
    main()
