import json
from datetime import datetime

from basyx.aas import model
from basyx.aas.adapter.json.json_serialization import AASToJsonEncoder

from windx_tracking.aas.builder import (
    build_event_submodel,
    build_shipment_shell,
    event_submodel_id,
    shipment_aas_id,
    shipment_global_asset_id,
)
from windx_tracking.models import Shipment, TrackingEvent
from windx_tracking.route import PORT_GATE


def _make_shipment() -> Shipment:
    return Shipment(shipment_id="SHP-0007", blade_serials=["BLD-0007-A", "BLD-0007-B", "BLD-0007-C"])


def _make_event(shipment: Shipment) -> TrackingEvent:
    return TrackingEvent(
        event_id="evt-abc",
        shipment=shipment,
        sequence=4,
        event_type="ARRIVAL",
        business_step="receiving",
        disposition="in_progress",
        station=PORT_GATE,
        timestamp=datetime(2026, 4, 1, 8, 15),
        remarks="Ankunft am Hafenterminal (Gate-In)",
    )


def test_build_shipment_shell_has_deterministic_identity():
    shipment = _make_shipment()
    shell = build_shipment_shell(shipment)

    assert isinstance(shell, model.AssetAdministrationShell)
    assert shell.id == shipment_aas_id(shipment)
    assert shell.asset_information.global_asset_id == shipment_global_asset_id(shipment)

    specific_ids = {sid.name: sid.value for sid in shell.asset_information.specific_asset_id}
    assert specific_ids["shipmentId"] == "SHP-0007"
    assert specific_ids["bladeSerial"] in shipment.blade_serials  # dict keys collide, at least one kept


def test_build_shipment_shell_is_deterministic_across_calls():
    shipment = _make_shipment()
    shell_a = build_shipment_shell(shipment)
    shell_b = build_shipment_shell(shipment)
    assert shell_a.id == shell_b.id


def test_build_event_submodel_contains_expected_elements():
    shipment = _make_shipment()
    event = _make_event(shipment)
    submodel = build_event_submodel(event)

    assert isinstance(submodel, model.Submodel)
    assert submodel.id == event_submodel_id(event)
    assert submodel.id_short == "TrackingEvent_04_ARRIVAL"

    by_id_short = {el.id_short: el for el in submodel.submodel_element}
    assert by_id_short["EventId"].value == "evt-abc"
    assert by_id_short["EventType"].value == "ARRIVAL"
    assert by_id_short["ShipmentId"].value == "SHP-0007"

    station = by_id_short["Station"]
    assert isinstance(station, model.SubmodelElementCollection)
    station_fields = {el.id_short: el.value for el in station.value}
    assert station_fields["UnLocode"] == PORT_GATE.un_locode
    assert station_fields["Name"] == PORT_GATE.name

    blade_serials = by_id_short["BladeSerials"]
    assert isinstance(blade_serials, model.SubmodelElementList)
    assert [el.value for el in blade_serials.value] == shipment.blade_serials


def test_event_submodel_serializes_with_all_elements():
    shipment = _make_shipment()
    event = _make_event(shipment)
    submodel = build_event_submodel(event)

    serialized = json.loads(json.dumps(submodel, cls=AASToJsonEncoder))

    assert serialized["modelType"] == "Submodel"
    assert serialized["id"] == event_submodel_id(event)
    id_shorts = {el["idShort"] for el in serialized["submodelElements"]}
    assert {"EventId", "EventType", "Station", "BladeSerials", "Timestamp"} <= id_shorts
