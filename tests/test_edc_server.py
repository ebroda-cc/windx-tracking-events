import json

import pytest

from windx_tracking.edc.server import EdcConnectorConfig, EdcConnectorRegistry, EdcManagementClient
from windx_tracking.route import CHECKPOINT, FACTORY, Station


class FakeResponse:
    def __init__(self, status_code: int):
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeSession:
    def __init__(self, post_status: int = 200, put_status: int = 200):
        self.post_status = post_status
        self.put_status = put_status
        self.calls: list[tuple[str, str, dict]] = []

    def post(self, url, data=None, headers=None, timeout=None):
        self.calls.append(("POST", url, headers or {}))
        return FakeResponse(self.post_status)

    def put(self, url, data=None, headers=None, timeout=None):
        self.calls.append(("PUT", url, headers or {}))
        return FakeResponse(self.put_status)


def test_registry_prefers_override_over_station_default():
    registry = EdcConnectorRegistry(
        overrides={FACTORY.code: EdcConnectorConfig(management_url="https://override.example.com")}
    )
    assert registry.config_for(FACTORY).management_url == "https://override.example.com"


def test_registry_falls_back_to_station_default():
    registry = EdcConnectorRegistry()
    assert registry.config_for(FACTORY).management_url == FACTORY.edc_management_url


def test_registry_raises_when_no_connector_available():
    bare_station = Station(code="STA-NONE", name="Ohne Connector", station_type="HUB")
    registry = EdcConnectorRegistry()
    with pytest.raises(ValueError):
        registry.config_for(bare_station)


def test_registry_from_json_file_accepts_plain_url_and_object_form(tmp_path):
    config_path = tmp_path / "edc.json"
    config_path.write_text(
        json.dumps(
            {
                CHECKPOINT.code: "https://checkpoint.example.com/management",
                FACTORY.code: {
                    "management_url": "https://factory.example.com/management",
                    "api_key": "secret-key",
                },
            }
        )
    )

    registry = EdcConnectorRegistry.from_json_file(config_path)

    assert registry.config_for(CHECKPOINT).management_url == "https://checkpoint.example.com/management"
    assert registry.config_for(CHECKPOINT).api_key is None

    factory_config = registry.config_for(FACTORY)
    assert factory_config.management_url == "https://factory.example.com/management"
    assert factory_config.api_key == "secret-key"


def test_create_or_update_asset_posts_and_includes_api_key_header():
    session = FakeSession(post_status=201)
    client = EdcManagementClient(session=session)
    config = EdcConnectorConfig(management_url="http://localhost:9191/management", api_key="k1")

    response = client.create_or_update_asset(config, "asset-1", {"@id": "asset-1"})

    assert response.status_code == 201
    method, url, headers = session.calls[0]
    assert method == "POST"
    assert url == "http://localhost:9191/management/v3/assets"
    assert headers["X-Api-Key"] == "k1"


def test_create_or_update_falls_back_to_put_on_conflict():
    session = FakeSession(post_status=409, put_status=200)
    client = EdcManagementClient(session=session)
    config = EdcConnectorConfig(management_url="http://localhost:9191/management")

    response = client.create_or_update_policy_definition(config, "policy-1", {"@id": "policy-1"})

    assert response.status_code == 200
    assert session.calls[0][:2] == ("POST", "http://localhost:9191/management/v3/policydefinitions")
    assert session.calls[1][:2] == (
        "PUT",
        "http://localhost:9191/management/v3/policydefinitions/policy-1",
    )


def test_create_or_update_contract_definition_uses_correct_path():
    session = FakeSession()
    client = EdcManagementClient(session=session)
    config = EdcConnectorConfig(management_url="http://localhost:9191/management")

    client.create_or_update_contract_definition(config, "cd-1", {"@id": "cd-1"})

    assert session.calls[0][1] == "http://localhost:9191/management/v3/contractdefinitions"
