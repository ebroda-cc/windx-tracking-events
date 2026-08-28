"""Verbindet Tracking-Events, AAS-Objektaufbau und Upload/Export.

Fuer jedes Event wird -- am fuer die jeweilige Station zustaendigen
AAS-Server -- sichergestellt, dass die Shell der Sendung dort existiert
(create-if-missing), anschliessend das Event-Submodel angelegt/aktualisiert
und der Shell als Submodel-Referenz hinzugefuegt.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

import requests
from basyx.aas.adapter.json.json_serialization import AASToJsonEncoder

from ..models import TrackingEvent
from .builder import build_event_submodel, build_shipment_shell
from .server import AasServerClient, AasServerRegistry

_OK_STATUS_CODES = (200, 201, 204)


def _raise_for_unexpected_status(response: requests.Response) -> None:
    if response.status_code not in _OK_STATUS_CODES:
        response.raise_for_status()


def upload_events_as_aas(
    events: Iterable[TrackingEvent],
    registry: AasServerRegistry,
    client: AasServerClient | None = None,
) -> None:
    """Laedt fuer jedes Event Shell (bei Bedarf) und Submodel auf den fuer
    die jeweilige Station zustaendigen AAS-Server hoch."""

    client = client or AasServerClient()
    known_shells: set[tuple[str, str]] = set()

    for event in events:
        base_url = registry.url_for(event.station)
        shell = build_shipment_shell(event.shipment)

        if (base_url, shell.id) not in known_shells:
            _raise_for_unexpected_status(client.upload_shell(base_url, shell))
            known_shells.add((base_url, shell.id))

        submodel = build_event_submodel(event)
        _raise_for_unexpected_status(client.upload_submodel(base_url, submodel))
        _raise_for_unexpected_status(client.add_submodel_ref(base_url, shell.id, submodel))


def export_events_as_aas(events: Iterable[TrackingEvent], output_dir: Path) -> None:
    """Schreibt Shell- und Submodel-JSON je Event lokal, ohne einen
    AAS-Server anzusprechen (z. B. fuer Tests ohne laufende Server oder zur
    Kontrolle vor dem eigentlichen Upload)."""

    output_dir.mkdir(parents=True, exist_ok=True)
    written_shells: set[str] = set()

    for event in events:
        shell = build_shipment_shell(event.shipment)
        if shell.id not in written_shells:
            shell_path = output_dir / f"{event.shipment.shipment_id}.aas-shell.json"
            shell_path.write_text(
                json.dumps(shell, cls=AASToJsonEncoder, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            written_shells.add(shell.id)

        submodel = build_event_submodel(event)
        submodel_path = output_dir / f"{event.file_stem}.aas-submodel.json"
        submodel_path.write_text(
            json.dumps(submodel, cls=AASToJsonEncoder, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
