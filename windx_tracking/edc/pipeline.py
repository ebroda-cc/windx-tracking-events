"""Bietet je Location die dort vorhandene Shipment-AAS als
Dataspace-Asset ueber den fuer diese Location zustaendigen EDC-Connector
an (Asset + Policy Definition + Contract Definition).

Analog zur AAS-Pipeline (:mod:`windx_tracking.aas.pipeline`) wird pro
Sendung an jeder durchlaufenen Location genau ein Angebot angelegt --
jede Location bietet damit ihre eigene, lokale Sicht auf die (identisch
identifizierte) Sendungs-AAS unabhaengig im Datenraum an.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

import requests

from ..aas.builder import shipment_aas_id
from ..aas.server import AasServerRegistry
from ..models import TrackingEvent
from .builder import build_asset, build_contract_definition, build_policy_definition
from .server import EdcConnectorRegistry, EdcManagementClient

_OK_STATUS_CODES = (200, 201, 204)


def _raise_for_unexpected_status(response: requests.Response) -> None:
    if response.status_code not in _OK_STATUS_CODES:
        response.raise_for_status()


def offer_events_as_dataspace_assets(
    events: Iterable[TrackingEvent],
    edc_registry: EdcConnectorRegistry,
    aas_registry: AasServerRegistry,
    client: EdcManagementClient | None = None,
) -> None:
    """Legt fuer jede Sendung an jeder Location, an der sie ein Event
    ausgeloest hat, Asset/Policy/Contract-Definition am dortigen
    EDC-Connector an (create-if-missing je Location+Sendung)."""

    client = client or EdcManagementClient()
    offered: set[tuple[str, str]] = set()  # (management_url, shipment_id)

    for event in events:
        station = event.station
        edc_config = edc_registry.config_for(station)
        key = (edc_config.management_url, event.shipment.shipment_id)
        if key in offered:
            continue
        offered.add(key)

        aas_server_url = aas_registry.url_for(station)
        shell_id = shipment_aas_id(event.shipment)

        asset = build_asset(event.shipment, shell_id, aas_server_url)
        _raise_for_unexpected_status(client.create_or_update_asset(edc_config, asset["@id"], asset))

        policy = build_policy_definition(event.shipment)
        _raise_for_unexpected_status(
            client.create_or_update_policy_definition(edc_config, policy["@id"], policy)
        )

        contract_definition = build_contract_definition(event.shipment)
        _raise_for_unexpected_status(
            client.create_or_update_contract_definition(
                edc_config, contract_definition["@id"], contract_definition
            )
        )


def export_events_as_dataspace_assets(
    events: Iterable[TrackingEvent],
    aas_registry: AasServerRegistry,
    output_dir: Path,
) -> None:
    """Schreibt Asset-/Policy-/Contract-Definition-JSON je Location+Sendung
    lokal, ohne einen EDC-Connector anzusprechen."""

    output_dir.mkdir(parents=True, exist_ok=True)
    written: set[tuple[str, str]] = set()  # (station_code, shipment_id)

    for event in events:
        station = event.station
        key = (station.code, event.shipment.shipment_id)
        if key in written:
            continue
        written.add(key)

        aas_server_url = aas_registry.url_for(station)
        shell_id = shipment_aas_id(event.shipment)

        asset = build_asset(event.shipment, shell_id, aas_server_url)
        policy = build_policy_definition(event.shipment)
        contract_definition = build_contract_definition(event.shipment)

        prefix = f"{station.code}_{event.shipment.shipment_id}"
        (output_dir / f"{prefix}.asset.json").write_text(
            json.dumps(asset, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        (output_dir / f"{prefix}.policy.json").write_text(
            json.dumps(policy, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        (output_dir / f"{prefix}.contract-definition.json").write_text(
            json.dumps(contract_definition, indent=2, ensure_ascii=False), encoding="utf-8"
        )
