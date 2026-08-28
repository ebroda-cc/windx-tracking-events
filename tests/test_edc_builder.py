from windx_tracking.edc.builder import (
    build_asset,
    build_contract_definition,
    build_policy_definition,
    shipment_asset_id,
    shipment_contract_definition_id,
    shipment_policy_id,
)
from windx_tracking.models import Shipment


def _make_shipment() -> Shipment:
    return Shipment(shipment_id="SHP-0042", blade_serials=["BLD-0042-A", "BLD-0042-B"])


def test_build_asset_points_to_shell_url_on_local_aas_server():
    shipment = _make_shipment()
    shell_id = "https://example.org/windx-tracking/aas/shipment/SHP-0042"

    asset = build_asset(shipment, shell_id, "http://localhost:8081")

    assert asset["@id"] == shipment_asset_id(shipment)
    assert asset["dataAddress"]["type"] == "HttpData"
    assert asset["dataAddress"]["baseUrl"].startswith("http://localhost:8081/shells/")
    assert asset["properties"]["windx:shipmentId"] == "SHP-0042"
    assert asset["properties"]["windx:bladeSerials"] == shipment.blade_serials


def test_build_asset_strips_trailing_slash_from_server_url():
    shipment = _make_shipment()
    asset = build_asset(shipment, "urn:some:shell", "http://localhost:8081/")
    assert "//shells" not in asset["dataAddress"]["baseUrl"]


def test_build_policy_definition_is_permissive_demo_policy():
    shipment = _make_shipment()
    policy = build_policy_definition(shipment)

    assert policy["@id"] == shipment_policy_id(shipment)
    assert policy["policy"]["@type"] == "Set"
    assert policy["policy"]["permission"] == []


def test_build_contract_definition_references_asset_and_policy():
    shipment = _make_shipment()
    contract_definition = build_contract_definition(shipment)

    assert contract_definition["@id"] == shipment_contract_definition_id(shipment)
    assert contract_definition["accessPolicyId"] == shipment_policy_id(shipment)
    assert contract_definition["contractPolicyId"] == shipment_policy_id(shipment)

    selector = contract_definition["assetsSelector"][0]
    assert selector["operandRight"] == shipment_asset_id(shipment)
    assert selector["operator"] == "="
