import json

import pytest

from windx_tracking.aas.builder import build_event_submodel, build_shipment_shell
from windx_tracking.aas.server import AasServerClient, AasServerRegistry, base64url_encode
from windx_tracking.models import Shipment, TrackingEvent
from windx_tracking.route import CHECKPOINT, FACTORY
from datetime import datetime


class FakeResponse:
    def __init__(self, status_code: int):
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeSession:
    """Records calls instead of performing real HTTP requests."""

    def __init__(self, post_status: int = 201, put_status: int = 200):
        self.post_status = post_status
        self.put_status = put_status
        self.calls: list[tuple[str, str]] = []

    def post(self, url, data=None, headers=None, timeout=None):
        self.calls.append(("POST", url))
        return FakeResponse(self.post_status)

    def put(self, url, data=None, headers=None, timeout=None):
        self.calls.append(("PUT", url))
        return FakeResponse(self.put_status)

    def get(self, url, timeout=None):
        self.calls.append(("GET", url))
        return FakeResponse(200)


def test_base64url_encode_is_url_safe():
    encoded = base64url_encode("https://example.org/windx-tracking/aas/shipment/SHP-0001")
    assert "+" not in encoded and "/" not in encoded


def test_registry_prefers_override_over_station_default():
    registry = AasServerRegistry(overrides={FACTORY.code: "https://override.example.com/aas"})
    assert registry.url_for(FACTORY) == "https://override.example.com/aas"


def test_registry_falls_back_to_station_default():
    registry = AasServerRegistry()
    assert registry.url_for(FACTORY) == FACTORY.aas_server_url.rstrip("/")


def test_registry_raises_when_no_url_available():
    from windx_tracking.route import Station

    bare_station = Station(code="STA-NONE", name="Ohne Server", station_type="HUB")
    registry = AasServerRegistry()
    with pytest.raises(ValueError):
        registry.url_for(bare_station)


def test_registry_from_json_file(tmp_path):
    config_path = tmp_path / "servers.json"
    config_path.write_text(json.dumps({CHECKPOINT.code: "https://checkpoint.example.com"}))

    registry = AasServerRegistry.from_json_file(config_path)
    assert registry.url_for(CHECKPOINT) == "https://checkpoint.example.com"


def test_upload_shell_creates_via_post():
    session = FakeSession(post_status=201)
    client = AasServerClient(session=session)
    shipment = Shipment(shipment_id="SHP-0001", blade_serials=["BLD-0001-A"])
    shell = build_shipment_shell(shipment)

    response = client.upload_shell("http://localhost:8081", shell)

    assert response.status_code == 201
    assert session.calls == [("POST", "http://localhost:8081/shells")]


def test_upload_shell_falls_back_to_put_on_conflict():
    session = FakeSession(post_status=409, put_status=200)
    client = AasServerClient(session=session)
    shipment = Shipment(shipment_id="SHP-0001", blade_serials=["BLD-0001-A"])
    shell = build_shipment_shell(shipment)

    response = client.upload_shell("http://localhost:8081", shell)

    assert response.status_code == 200
    assert session.calls[0] == ("POST", "http://localhost:8081/shells")
    assert session.calls[1][0] == "PUT"
    assert session.calls[1][1].startswith("http://localhost:8081/shells/")


def test_add_submodel_ref_posts_to_submodel_refs_endpoint():
    session = FakeSession()
    client = AasServerClient(session=session)
    shipment = Shipment(shipment_id="SHP-0001", blade_serials=["BLD-0001-A"])
    event = TrackingEvent(
        event_id="evt-1",
        shipment=shipment,
        sequence=1,
        event_type="PICKUP",
        business_step="staging_outbound",
        disposition="staging_outbound",
        station=FACTORY,
        timestamp=datetime(2026, 1, 1),
        remarks="",
    )
    submodel = build_event_submodel(event)
    shell = build_shipment_shell(shipment)

    response = client.add_submodel_ref("http://localhost:8081", shell.id, submodel)

    assert response.status_code == 201
    assert session.calls[0][0] == "POST"
    assert session.calls[0][1].endswith("/submodel-refs")
