"""Baut JSON-LD-Bodies fuer die EDC Management API (Eclipse Dataspace
Components), um die pro Location vorhandene Shipment-AAS als
Dataspace-Asset anzubieten.

Pro Sendung wird an jeder Location, an der die Sendung ein Tracking-Event
ausgeloest hat, ein eigenes **Asset** angelegt, dessen ``dataAddress`` auf
die dort liegende Shell dieser Sendung zeigt (siehe
``windx_tracking.aas``), dazu eine sehr einfache **Policy Definition**
(Demo-Policy ohne Einschraenkungen) und eine **Contract Definition**, die
Asset und Policy zu einem im Datenraum abschliessbaren Angebot verbindet.

Hinweis: Die JSON-LD-Struktur folgt der EDC Management API V3 (Kontext
``https://w3id.org/edc/v0.0.1/ns/``), wie sie z. B. vom Eclipse-EDC-
Connector und darauf aufbauenden Datenraum-Implementierungen verwendet
wird. Exakte Felder/Pfade koennen sich je nach konkreter
Connector-Version/-Distribution leicht unterscheiden -- die Struktur ist
bewusst vereinfacht/illustrativ, analog zu den EDI-/EPCIS-/AAS-
Darstellungen an anderer Stelle in diesem Projekt. Insbesondere die
Policy ist eine reine Demo-Policy: in einem echten Datenraum steht hier
eine tatsaechliche ODRL-Policy (Teilnehmerkreis, Zweckbindung, ...).
"""

from __future__ import annotations

from ..aas.server import base64url_encode
from ..models import Shipment

EDC_CONTEXT = {"@vocab": "https://w3id.org/edc/v0.0.1/ns/"}
ODRL_JSONLD_CONTEXT = "http://www.w3.org/ns/odrl.jsonld"
ODRL_NAMESPACE = "http://www.w3.org/ns/odrl/2/"
EDC_ASSET_ID_PROPERTY = "https://w3id.org/edc/v0.0.1/ns/id"


def shipment_asset_id(shipment: Shipment) -> str:
    return f"windx-shipment-{shipment.shipment_id}"


def shipment_policy_id(shipment: Shipment) -> str:
    return f"{shipment_asset_id(shipment)}-policy"


def shipment_contract_definition_id(shipment: Shipment) -> str:
    return f"{shipment_asset_id(shipment)}-contract-definition"


def build_asset(shipment: Shipment, shell_id: str, aas_server_url: str) -> dict:
    """Asset, dessen ``dataAddress`` auf die Shell dieser Sendung am
    jeweils lokalen AAS-Server zeigt. ``proxyPath`` erlaubt es Konsumenten,
    ueber die Data Plane auch benachbarte Ressourcen (z. B.
    ``/submodel-refs``) desselben Servers anzusprechen."""

    shell_url = f"{aas_server_url.rstrip('/')}/shells/{base64url_encode(shell_id)}"
    return {
        "@context": EDC_CONTEXT,
        "@id": shipment_asset_id(shipment),
        "properties": {
            "name": f"Rotorblatt-Sendung {shipment.shipment_id} (AAS)",
            "contenttype": "application/json",
            "windx:shipmentId": shipment.shipment_id,
            "windx:bladeSerials": list(shipment.blade_serials),
            "windx:aasShellId": shell_id,
        },
        "dataAddress": {
            "type": "HttpData",
            "baseUrl": shell_url,
            "proxyPath": "true",
        },
    }


def build_policy_definition(shipment: Shipment) -> dict:
    """Sehr permissive Demo-Policy (keine Einschraenkungen/Pflichten)."""
    return {
        "@context": {**EDC_CONTEXT, "odrl": ODRL_NAMESPACE},
        "@id": shipment_policy_id(shipment),
        "policy": {
            "@context": ODRL_JSONLD_CONTEXT,
            "@type": "Set",
            "permission": [],
        },
    }


def build_contract_definition(shipment: Shipment) -> dict:
    policy_id = shipment_policy_id(shipment)
    return {
        "@context": EDC_CONTEXT,
        "@id": shipment_contract_definition_id(shipment),
        "accessPolicyId": policy_id,
        "contractPolicyId": policy_id,
        "assetsSelector": [
            {
                "operandLeft": EDC_ASSET_ID_PROPERTY,
                "operator": "=",
                "operandRight": shipment_asset_id(shipment),
            }
        ],
    }
