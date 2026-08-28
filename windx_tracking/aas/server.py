"""Registry fuer pro-Location AAS-Server-URLs sowie ein minimaler
HTTP-Client fuer die AAS-Repository-API (IDTA "Details of the Asset
Administration Shell Part 2: Application Programming Interfaces",
V3.1 -- Asset Administration Shell Repository / Submodel Repository
Service Specification).

Angenommen wird ein Server, der Shells und Submodels unter einer
gemeinsamen Basis-URL anbietet (``{base_url}/shells``,
``{base_url}/submodels``), wie z. B. die BaSyx AAS-Environment oder der
FA³ST Service. Die Kern-Endpunkte sind zwischen API V3.0 und V3.1
unveraendert.
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Union

import requests
from basyx.aas import model
from basyx.aas.adapter.json.json_serialization import AASToJsonEncoder

from ..route import Station

# HTTP-Statuscodes, die "existiert bereits" signalisieren und einen Fallback
# von create (POST) auf update (PUT) ausloesen.
_ALREADY_EXISTS_STATUS_CODES = (409,)


def base64url_encode(identifier: str) -> str:
    """Kodiert eine AAS-/Submodel-ID fuer die Verwendung als Pfadsegment,
    wie von der AAS-API fuer ``{aasIdentifier}``/``{submodelIdentifier}``
    gefordert (RFC 4648 Base64url)."""
    return base64.urlsafe_b64encode(identifier.encode("utf-8")).decode("ascii")


def _to_json(obj: object) -> str:
    return json.dumps(obj, cls=AASToJsonEncoder)


@dataclass
class AasServerRegistry:
    """Ordnet Stationen (Locations) ihre jeweilige AAS-Server-Basis-URL zu.

    Fehlt ein Eintrag fuer eine Station, wird auf ``Station.aas_server_url``
    zurueckgefallen. So kann pro Umgebung/Lauf konfiguriert werden, welcher
    Server tatsaechlich fuer welche Location angesprochen wird, ohne die
    Routendefinition selbst aendern zu muessen.
    """

    overrides: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_json_file(cls, path: Union[str, Path]) -> "AasServerRegistry":
        """Laedt Overrides aus einer JSON-Datei der Form
        ``{"STA-FACTORY": "https://factory.example.com/aas", ...}``."""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls(overrides={str(k): str(v) for k, v in data.items()})

    def url_for(self, station: Station) -> str:
        base_url = self.overrides.get(station.code) or station.aas_server_url
        if not base_url:
            raise ValueError(
                f"Keine AAS-Server-URL fuer Station {station.code!r} konfiguriert "
                "(weder Override noch Station.aas_server_url gesetzt)"
            )
        return base_url.rstrip("/")


class AasServerClient:
    """Minimaler HTTP-Client fuer Shells, Submodels und Submodel-Referenzen
    einer AAS-Repository-API. Create ist idempotent umgesetzt: zuerst wird
    per POST angelegt, existiert die ID bereits, wird per PUT aktualisiert.
    """

    def __init__(self, timeout: float = 10.0, session: Optional[requests.Session] = None) -> None:
        self.timeout = timeout
        self.session = session or requests.Session()

    def upload_shell(self, base_url: str, shell: model.AssetAdministrationShell) -> requests.Response:
        return self._create_or_update(f"{base_url}/shells", shell.id, shell)

    def upload_submodel(self, base_url: str, submodel: model.Submodel) -> requests.Response:
        return self._create_or_update(f"{base_url}/submodels", submodel.id, submodel)

    def add_submodel_ref(
        self, base_url: str, shell_id: str, submodel: model.Submodel
    ) -> requests.Response:
        """Haengt eine Referenz auf ``submodel`` an die Shell ``shell_id``."""
        reference = model.ModelReference.from_referable(submodel)
        url = f"{base_url}/shells/{base64url_encode(shell_id)}/submodel-refs"
        return self.session.post(
            url,
            data=_to_json(reference),
            headers={"Content-Type": "application/json"},
            timeout=self.timeout,
        )

    def _create_or_update(self, collection_url: str, identifier: str, obj: object) -> requests.Response:
        body = _to_json(obj)
        headers = {"Content-Type": "application/json"}
        response = self.session.post(collection_url, data=body, headers=headers, timeout=self.timeout)
        if response.status_code in _ALREADY_EXISTS_STATUS_CODES:
            item_url = f"{collection_url}/{base64url_encode(identifier)}"
            response = self.session.put(item_url, data=body, headers=headers, timeout=self.timeout)
        return response
