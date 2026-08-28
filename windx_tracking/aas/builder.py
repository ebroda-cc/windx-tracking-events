"""Baut AAS-Objekte (Metamodell V3, ueber ``basyx-python-sdk``) aus
Sendungen und Tracking-Events.

Modellierung:

* Jeder Transport (:class:`~windx_tracking.models.Shipment`) bekommt genau
  eine **Asset Administration Shell** (Asset = die Sendung / die darin
  transportierten Rotorblaetter, als ``globalAssetId`` plus
  ``specificAssetId`` je Blatt-Seriennummer).
* Jedes **Tracking-Event** wird als eigenes **Submodel** modelliert
  (Pendant zum EDI- und EPCIS-Event) und der Shell per Submodel-Referenz
  hinzugefuegt.

Da dieselbe Sendung auf ihrem Weg mehrere, jeweils an eine Station
gebundene AAS-Server durchlaeuft (siehe :mod:`.server`), wird die Shell an
jedem Server, an dem ein Event fuer diese Sendung anfaellt, bei Bedarf neu
angelegt (create-if-missing) und lokal um das dort erzeugte Submodel
ergaenzt -- jeder Standort haelt also seine eigene, lokale Sicht auf die
(ansonsten identisch identifizierte) Shell.

Hinweis: Die ``semanticId``-Verweise nutzen einen eigenen, fiktiven
Namespace (``https://example.org/windx-tracking/...``) und sind keine
offiziellen IDTA-Submodel-Templates, sondern ein fuer diese Simulation
entworfenes, einfaches Schema -- analog zu den bereits vereinfachten
EDI-/EPCIS-Darstellungen.
"""

from __future__ import annotations

import datetime as dt

from basyx.aas import model

from ..models import Shipment, TrackingEvent

NAMESPACE = "https://example.org/windx-tracking"


def _external_reference(uri: str) -> model.ExternalReference:
    return model.ExternalReference((model.Key(model.KeyTypes.GLOBAL_REFERENCE, uri),))


def _semantic_id(suffix: str) -> model.ExternalReference:
    return _external_reference(f"{NAMESPACE}/concepts/{suffix}")


def shipment_aas_id(shipment: Shipment) -> str:
    return f"{NAMESPACE}/aas/shipment/{shipment.shipment_id}"


def shipment_global_asset_id(shipment: Shipment) -> str:
    return f"{NAMESPACE}/asset/shipment/{shipment.shipment_id}"


def event_submodel_id(event: TrackingEvent) -> str:
    return f"{NAMESPACE}/submodel/trackingevent/{event.event_id}"


def build_shipment_shell(shipment: Shipment) -> model.AssetAdministrationShell:
    """Erzeugt die Asset Administration Shell fuer eine Sendung.

    Die ``id`` und ``globalAssetId`` sind deterministisch aus der
    ``shipment_id`` abgeleitet, sodass an unterschiedlichen AAS-Servern
    (Locations) jeweils eine Shell mit derselben Identitaet entsteht.
    """
    asset_information = model.AssetInformation(
        asset_kind=model.AssetKind.INSTANCE,
        global_asset_id=shipment_global_asset_id(shipment),
        specific_asset_id=[
            model.SpecificAssetId(name="shipmentId", value=shipment.shipment_id),
            *[
                model.SpecificAssetId(name="bladeSerial", value=serial)
                for serial in shipment.blade_serials
            ],
        ],
        asset_type=f"{NAMESPACE}/asset-types/BladeShipment",
    )
    return model.AssetAdministrationShell(
        asset_information=asset_information,
        id_=shipment_aas_id(shipment),
        id_short=f"Shipment_{shipment.shipment_id}",
    )


def _station_collection(event: TrackingEvent) -> model.SubmodelElementCollection:
    station = event.station
    return model.SubmodelElementCollection(
        id_short="Station",
        semantic_id=_semantic_id("station"),
        value=[
            model.Property("Code", str, station.code, semantic_id=_semantic_id("station/code")),
            model.Property("Name", str, station.name, semantic_id=_semantic_id("station/name")),
            model.Property(
                "StationType", str, station.station_type, semantic_id=_semantic_id("station/type")
            ),
            model.Property(
                "UnLocode", str, station.un_locode, semantic_id=_semantic_id("station/unLocode")
            ),
            model.Property("Gln", str, station.gln, semantic_id=_semantic_id("station/gln")),
        ],
    )


def _blade_serial_list(shipment: Shipment) -> model.SubmodelElementList:
    return model.SubmodelElementList(
        id_short="BladeSerials",
        semantic_id=_semantic_id("bladeSerials"),
        type_value_list_element=model.Property,
        value_type_list_element=str,
        value=[
            model.Property(f"BladeSerial{i}", str, serial)
            for i, serial in enumerate(shipment.blade_serials, start=1)
        ],
    )


def build_event_submodel(event: TrackingEvent) -> model.Submodel:
    """Erzeugt das Submodel, das genau ein Tracking-Event abbildet."""

    shipment = event.shipment
    elements: list[model.SubmodelElement] = [
        model.Property("EventId", str, event.event_id, semantic_id=_semantic_id("event/id")),
        model.Property(
            "ShipmentId", str, shipment.shipment_id, semantic_id=_semantic_id("event/shipmentId")
        ),
        model.Property("Sequence", int, event.sequence, semantic_id=_semantic_id("event/sequence")),
        model.Property("EventType", str, event.event_type, semantic_id=_semantic_id("event/type")),
        model.Property(
            "BusinessStep", str, event.business_step, semantic_id=_semantic_id("event/bizStep")
        ),
        model.Property(
            "Disposition", str, event.disposition, semantic_id=_semantic_id("event/disposition")
        ),
        model.Property(
            "Timestamp", dt.datetime, event.timestamp, semantic_id=_semantic_id("event/timestamp")
        ),
        model.Property(
            "Carrier", str, shipment.carrier, semantic_id=_semantic_id("event/carrier")
        ),
        model.Property(
            "ModeOfTransport",
            str,
            shipment.mode_of_transport,
            semantic_id=_semantic_id("event/modeOfTransport"),
        ),
        model.Property("Remarks", str, event.remarks, semantic_id=_semantic_id("event/remarks")),
        _station_collection(event),
        _blade_serial_list(shipment),
    ]

    return model.Submodel(
        id_=event_submodel_id(event),
        id_short=f"TrackingEvent_{event.sequence:02d}_{event.event_type}",
        submodel_element=elements,
        semantic_id=_semantic_id("trackingEvent"),
        kind=model.ModellingKind.INSTANCE,
    )
