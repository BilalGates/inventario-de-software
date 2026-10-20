import httpx
import pytest

from app.connectors.base import ConnectorError
from app.connectors.intune import IntuneConnector, map_device
from tests.fakes import FakeGraph, device

APPS = {
    "Google Chrome|Google LLC|129.0.1": ["intune-1", "intune-2", "intune-3"],
    "7-Zip 23.01 (x64)|Igor Pavlov|23.01": ["intune-1"],
    "Notepad++|Notepad++ Team|8.6": ["intune-2"],
}


def test_pagination_and_mapping():
    fake = FakeGraph([device(i) for i in range(1, 6)], APPS, page_size=2)
    result = IntuneConnector(fake.client()).extract({}, lambda m: None)
    assert len(result.devices) == 5  # 3 páginas
    assert result.complete
    assert len(result.installs) == 5
    assert result.software_complete_for == {f"intune-{i}" for i in range(1, 6)}
    dev = result.devices[0]
    assert dev.ram_bytes == 16 * 1024**3  # leída por dispositivo porque la lista devuelve 0
    assert dev.mac_ethernet is None  # cadena vacía -> desconocido, no ""
    assert dev.ids == {"intune_device_id": "intune-1", "entra_device_id": "entra-1"}


def test_unknown_values_are_not_invented():
    rec = map_device(device(1, serialNumber="", enrolledDateTime="0001-01-01T00:00:00Z", isEncrypted=None,
                            azureADDeviceId="00000000-0000-0000-0000-000000000000", userPrincipalName=None))
    assert rec.serial_number is None and rec.enrolled_at is None and rec.encrypted is None
    assert "entra_device_id" not in rec.ids and rec.user_upn is None


def test_retry_after_on_throttling():
    fake = FakeGraph([device(1)], {})
    state = {"n": 0}
    sleeps = []

    def throttle(req):
        if req.url.path.endswith("/managedDevices") and state["n"] < 2:
            state["n"] += 1
            return httpx.Response(429, headers={"Retry-After": "7"})
        return None

    fake.fail = throttle
    client = fake.client()
    client.sleep = sleeps.append
    result = IntuneConnector(client).extract({}, lambda m: None)
    assert len(result.devices) == 1
    assert sleeps == [7.0, 7.0]
    assert client.throttled_count == 2


def test_permission_error_is_not_retried():
    fake = FakeGraph([device(1)], {})
    fake.fail = lambda req: httpx.Response(403, json={"error": {"code": "Forbidden", "message": "secret detail"}})
    with pytest.raises(ConnectorError) as err:
        IntuneConnector(fake.client()).extract({}, lambda m: None)
    assert err.value.kind == "permission"
    assert "secret detail" not in str(err.value)


def test_partial_software_marks_incomplete():
    fake = FakeGraph([device(1), device(2)], APPS)
    fake.fail = lambda req: (httpx.Response(500) if req.url.path.endswith("app-1/managedDevices") else None)
    result = IntuneConnector(fake.client()).extract({}, lambda m: None)
    assert result.devices_complete
    assert not result.complete
    assert result.software_complete_for == set()


def test_network_errors_retry_then_fail():
    calls = {"n": 0}

    def handler(req):
        if req.url.host == "login.microsoftonline.com":
            return httpx.Response(200, json={"access_token": "t", "expires_in": 3600})
        calls["n"] += 1
        raise httpx.ConnectError("down")

    from app.connectors.graph import GraphClient

    client = GraphClient("t", "c", "s", http=httpx.Client(transport=httpx.MockTransport(handler)),
                         sleep=lambda s: None, max_retries=2)
    with pytest.raises(ConnectorError) as err:
        client.get("/v1.0/deviceManagement/managedDevices")
    assert err.value.kind == "network" and calls["n"] == 3


def test_auth_failure():
    def handler(req):
        return httpx.Response(401, json={"error": "invalid_client", "error_description": "AADSTS7000215"})

    from app.connectors.graph import GraphClient

    client = GraphClient("t", "c", "s", http=httpx.Client(transport=httpx.MockTransport(handler)))
    with pytest.raises(ConnectorError) as err:
        client.get("/v1.0/x")
    assert err.value.kind == "auth"


def test_per_device_strategy():
    fake = FakeGraph([device(1), device(2)], APPS)
    result = IntuneConnector(fake.client()).extract({"software_strategy": "per_device"}, lambda m: None)
    assert result.complete and len(result.installs) == 4


def test_per_app_skips_apps_without_devices_and_reports_progress():
    fake = FakeGraph([device(1), device(2)], {"A|x|1": ["intune-1"], "B|x|1": ["intune-2"], "C|x|1": []})
    fake.apps[2]["deviceCount"] = 0
    logs = []
    result = IntuneConnector(fake.client()).extract({"fetch_hardware_details": False}, logs.append)
    assert len(result.installs) == 2 and result.complete
    assert not any(c.endswith("/app-2/managedDevices") for c in fake.calls)  # sin dispositivos: no se consulta
    assert any("aplicaciones 2/2" in m for m in logs)


def test_per_device_does_not_trust_empty_lists():
    fake = FakeGraph([device(1), device(2)], {"A|x|1": ["intune-1"]})
    result = IntuneConnector(fake.client()).extract({"software_strategy": "per_device",
                                                      "fetch_hardware_details": False}, lambda m: None)
    assert len(result.installs) == 1
    assert result.software_complete_for == {"intune-1"}  # el equipo vacío no permite inferir bajas
    assert result.installs[0].publisher == "x"  # el editor sale del catálogo, no del $expand de beta
    assert all(i.source_app_id != "pkg-sistema" for i in result.installs)
    assert sum(c.startswith("GET /beta/deviceManagement/managedDevices/") for c in fake.calls) == 2  # una por equipo
