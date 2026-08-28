"""Registry fuer pro-Location EDC-Connector-Endpunkte sowie ein minimaler
HTTP-Client fuer die EDC Management API (Assets, Policy-Definitions,
Contract-Definitions).

Analog zu :mod:`windx_tracking.aas.server` kann jede Station/Location
ihren eigenen EDC-Connector betreiben: die Registry loest je Station die
zustaendige Management-API-URL (und optional einen API-Key) auf.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Union

import requests

from ..route import Station


@dataclass(frozen=True)
class EdcConnectorConfig:
    management_url: str
    api_key: Optional[str] = None


@dataclass
class EdcConnectorRegistry:
    """Ordnet Stationen (Locations) ihren jeweils zustaendigen
    EDC-Connector zu. Fehlt ein Eintrag, wird auf
    ``Station.edc_management_url`` zurueckgefallen."""

    overrides: dict[str, EdcConnectorConfig] = field(default_factory=dict)

    @classmethod
    def from_json_file(cls, path: Union[str, Path]) -> "EdcConnectorRegistry":
        """Laedt Overrides aus einer JSON-Datei der Form
        ``{"STA-FACTORY": "https://factory.example.com/management"}`` oder,
        falls ein API-Key benoetigt wird,
        ``{"STA-FACTORY": {"management_url": "...", "api_key": "..."}}``."""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        overrides: dict[str, EdcConnectorConfig] = {}
        for code, value in data.items():
            if isinstance(value, str):
                overrides[code] = EdcConnectorConfig(management_url=value)
            else:
                overrides[code] = EdcConnectorConfig(
                    management_url=value["management_url"], api_key=value.get("api_key")
                )
        return cls(overrides=overrides)

    def config_for(self, station: Station) -> EdcConnectorConfig:
        if station.code in self.overrides:
            return self.overrides[station.code]
        if station.edc_management_url:
            return EdcConnectorConfig(management_url=station.edc_management_url)
        raise ValueError(
            f"Kein EDC-Connector fuer Station {station.code!r} konfiguriert "
            "(weder Override noch Station.edc_management_url gesetzt)"
        )


class EdcManagementClient:
    """Minimaler HTTP-Client fuer die EDC Management API v3
    (``/v3/assets``, ``/v3/policydefinitions``, ``/v3/contractdefinitions``).
    Create ist idempotent umgesetzt: zuerst POST, existiert die ID bereits
    (409), Fallback auf PUT."""

    def __init__(self, timeout: float = 10.0, session: Optional[requests.Session] = None) -> None:
        self.timeout = timeout
        self.session = session or requests.Session()

    def create_or_update_asset(
        self, config: EdcConnectorConfig, asset_id: str, body: dict
    ) -> requests.Response:
        return self._create_or_update(config, "/v3/assets", asset_id, body)

    def create_or_update_policy_definition(
        self, config: EdcConnectorConfig, policy_id: str, body: dict
    ) -> requests.Response:
        return self._create_or_update(config, "/v3/policydefinitions", policy_id, body)

    def create_or_update_contract_definition(
        self, config: EdcConnectorConfig, contract_definition_id: str, body: dict
    ) -> requests.Response:
        return self._create_or_update(config, "/v3/contractdefinitions", contract_definition_id, body)

    def _headers(self, config: EdcConnectorConfig) -> dict:
        headers = {"Content-Type": "application/json"}
        if config.api_key:
            headers["X-Api-Key"] = config.api_key
        return headers

    def _create_or_update(
        self, config: EdcConnectorConfig, path: str, identifier: str, body: dict
    ) -> requests.Response:
        url = f"{config.management_url.rstrip('/')}{path}"
        headers = self._headers(config)
        body_text = json.dumps(body)
        response = self.session.post(url, data=body_text, headers=headers, timeout=self.timeout)
        if response.status_code == 409:
            item_url = f"{url}/{identifier}"
            response = self.session.put(item_url, data=body_text, headers=headers, timeout=self.timeout)
        return response
