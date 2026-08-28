import json
import random
from datetime import datetime

from windx_tracking.aas.pipeline import export_events_as_aas, upload_events_as_aas
from windx_tracking.aas.server import AasServerClient, AasServerRegistry
from windx_tracking.des import Simulation
from windx_tracking.models import Shipment, TrackingEvent
from windx_tracking.route import DEFAULT_ROUTE
from windx_tracking.transport import start_transport


def _run_single_transport() -> list[TrackingEvent]:
    sim = Simulation()
    rng = random.Random(3)
    events: list[TrackingEvent] = []
    shipment = Shipment(shipment_id="SHP-0099", blade_serials=["BLD-A", "BLD-B"])
    start_transport(sim, shipment, DEFAULT_ROUTE, rng, datetime(2026, 1, 1), 0, events.append)
    sim.run()
    return events


def test_export_events_as_aas_writes_one_shell_and_one_submodel_per_event(tmp_path):
    events = _run_single_transport()

    export_events_as_aas(events, tmp_path)

    shell_files = list(tmp_path.glob("*.aas-shell.json"))
    submodel_files = list(tmp_path.glob("*.aas-submodel.json"))

    assert len(shell_files) == 1  # eine Sendung -> eine Shell, unabhaengig von der Event-Anzahl
    assert len(submodel_files) == len(events)

    shell_data = json.loads(shell_files[0].read_text())
    assert shell_data["modelType"] == "AssetAdministrationShell"

    submodel_data = json.loads(submodel_files[0].read_text())
    assert submodel_data["modelType"] == "Submodel"
    assert "submodelElements" in submodel_data


class _RecordingFakeSession:
    def __init__(self):
        self.calls: list[tuple[str, str]] = []

    class _Resp:
        status_code = 201

        def raise_for_status(self):
            pass

    def post(self, url, data=None, headers=None, timeout=None):
        self.calls.append(("POST", url))
        return self._Resp()

    def put(self, url, data=None, headers=None, timeout=None):
        self.calls.append(("PUT", url))
        return self._Resp()

    def get(self, url, timeout=None):
        self.calls.append(("GET", url))
        return self._Resp()


def test_upload_events_as_aas_uploads_shell_once_per_server_and_submodel_per_event():
    events = _run_single_transport()
    session = _RecordingFakeSession()
    client = AasServerClient(session=session)
    registry = AasServerRegistry()

    upload_events_as_aas(events, registry, client=client)

    shell_posts = [url for method, url in session.calls if method == "POST" and url.endswith("/shells")]
    submodel_posts = [
        url for method, url in session.calls if method == "POST" and url.endswith("/submodels")
    ]
    ref_posts = [url for method, url in session.calls if method == "POST" and url.endswith("/submodel-refs")]

    # Jede Station hat in der Standardroute ihren eigenen AAS-Server -> die
    # Shell wird einmal pro *Server* angelegt (nicht einmal insgesamt), aber
    # genau ein Submodel + eine Submodel-Referenz pro Event.
    distinct_servers = {e.station.aas_server_url for e in events}
    assert len(shell_posts) == len(distinct_servers)
    assert len(submodel_posts) == len(events)
    assert len(ref_posts) == len(events)


def test_upload_events_as_aas_routes_to_different_servers_per_station():
    events = _run_single_transport()
    session = _RecordingFakeSession()
    client = AasServerClient(session=session)
    registry = AasServerRegistry()

    upload_events_as_aas(events, registry, client=client)

    hosts = {url.split("/shells")[0] for method, url in session.calls if url.endswith("/shells")}
    hosts |= {url.split("/submodels")[0] for method, url in session.calls if "/submodels" in url and not url.endswith("/shells")}

    # Die Standardroute durchlaeuft mehrere Stationen mit unterschiedlichen
    # AAS-Server-URLs (siehe route.py) -> es muessen mehrere Hosts angesprochen werden.
    assert len({e.station.aas_server_url for e in events}) > 1
    assert len(hosts) > 1
