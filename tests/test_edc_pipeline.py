import json
import random
from datetime import datetime

from windx_tracking.aas.server import AasServerRegistry
from windx_tracking.des import Simulation
from windx_tracking.edc.pipeline import export_events_as_dataspace_assets, offer_events_as_dataspace_assets
from windx_tracking.edc.server import EdcConnectorRegistry, EdcManagementClient
from windx_tracking.models import Shipment, TrackingEvent
from windx_tracking.route import DEFAULT_ROUTE
from windx_tracking.transport import start_transport


def _run_single_transport() -> list[TrackingEvent]:
    sim = Simulation()
    rng = random.Random(11)
    events: list[TrackingEvent] = []
    shipment = Shipment(shipment_id="SHP-0055", blade_serials=["BLD-A", "BLD-B"])
    start_transport(sim, shipment, DEFAULT_ROUTE, rng, datetime(2026, 1, 1), 0, events.append)
    sim.run()
    return events


def test_export_events_as_dataspace_assets_writes_one_offer_per_location(tmp_path):
    events = _run_single_transport()
    aas_registry = AasServerRegistry()

    export_events_as_dataspace_assets(events, aas_registry, tmp_path)

    distinct_stations = {e.station.code for e in events}
    asset_files = list(tmp_path.glob("*.asset.json"))
    policy_files = list(tmp_path.glob("*.policy.json"))
    contract_files = list(tmp_path.glob("*.contract-definition.json"))

    assert len(asset_files) == len(distinct_stations)
    assert len(policy_files) == len(distinct_stations)
    assert len(contract_files) == len(distinct_stations)

    asset_data = json.loads(asset_files[0].read_text())
    assert asset_data["dataAddress"]["type"] == "HttpData"


class _RecordingFakeSession:
    class _Resp:
        status_code = 201

        def raise_for_status(self):
            pass

    def __init__(self):
        self.calls: list[tuple[str, str]] = []

    def post(self, url, data=None, headers=None, timeout=None):
        self.calls.append(("POST", url))
        return self._Resp()

    def put(self, url, data=None, headers=None, timeout=None):
        self.calls.append(("PUT", url))
        return self._Resp()


def test_offer_events_as_dataspace_assets_creates_one_offer_per_location():
    events = _run_single_transport()
    session = _RecordingFakeSession()
    client = EdcManagementClient(session=session)
    edc_registry = EdcConnectorRegistry()
    aas_registry = AasServerRegistry()

    offer_events_as_dataspace_assets(events, edc_registry, aas_registry, client=client)

    asset_posts = [url for method, url in session.calls if method == "POST" and url.endswith("/v3/assets")]
    policy_posts = [
        url for method, url in session.calls if method == "POST" and url.endswith("/v3/policydefinitions")
    ]
    contract_posts = [
        url for method, url in session.calls if method == "POST" and url.endswith("/v3/contractdefinitions")
    ]

    distinct_connectors = {e.station.edc_management_url for e in events}
    assert len(asset_posts) == len(distinct_connectors)
    assert len(policy_posts) == len(distinct_connectors)
    assert len(contract_posts) == len(distinct_connectors)
    assert len(distinct_connectors) > 1  # jede Location hat ihren eigenen EDC-Connector
