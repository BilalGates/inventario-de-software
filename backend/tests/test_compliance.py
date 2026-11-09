"""Conformidad de Intune: detalle del motivo, sincronización y acciones remotas."""
import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.connectors.intune import IntuneConnector
from app.connectors.intune_compliance import explain, fetch_compliance, reasons
from app.core.security import CurrentUser, get_current_user
from app.main import create_app
from app.models import AuditEvent, Device
from app.services import graph_session, runs
from tests.fakes import FakeGraph, device, policy

BITLOCKER = "Windows10CompliancePolicy.BitLockerEnabled"
SIGNATURES = "Windows10CompliancePolicy.SignatureOutOfDate"


def _fake() -> FakeGraph:
    fake = FakeGraph([device(1), device(2, complianceState="noncompliant")], {})
    fake.compliance["intune-2"] = [
        policy("Seguridad Windows", "nonCompliant", (BITLOCKER, "nonCompliant"), (SIGNATURES, "nonCompliant"),
               ("Windows10CompliancePolicy.SecureBootEnabled", "compliant")),
        policy("Default Device Compliance Policy", "compliant"),
    ]
    return fake


def test_explain_known_and_unknown_settings():
    assert explain(BITLOCKER, "BitLockerEnabled")[0] == "BitLocker desactivado"
    assert explain(SIGNATURES, None)[2] == "defender_signatures"
    assert explain("Custom.Raro", "Ajuste raro") == ("Ajuste raro", None, None)


def test_fetch_only_failing_policies_and_settings():
    details = fetch_compliance(_fake().client(), "intune-2")
    assert [p["name"] for p in details["policies"]] == ["Seguridad Windows"]
    assert [s["label"] for s in details["policies"][0]["settings"]] == [
        "BitLocker desactivado", "Firmas de Defender desactualizadas"]
    assert reasons(details) == ["BitLocker desactivado", "Firmas de Defender desactualizadas"]


def test_fetch_falls_back_to_beta_when_v1_has_no_settings():
    fake = FakeGraph([device(1)], {})
    fake.compliance["intune-1"] = [policy("Seguridad Windows", "nonCompliant")]
    fake.compliance_beta["intune-1"] = [policy("Seguridad Windows", "nonCompliant", (BITLOCKER, "nonCompliant"))]
    details = fetch_compliance(fake.client(), "intune-1")
    assert reasons(details) == ["BitLocker desactivado"]


def test_sync_stores_reasons_and_clears_them_when_compliant(db):
    fake = _fake()
    run = runs.enqueue(db, "intune", "manual", "tester")
    db.commit()
    runs.execute_run(db, run, factory=lambda src, params: IntuneConnector(fake.client()))
    pc2 = db.execute(select(Device).where(Device.hostname == "PC-002")).scalar_one()
    assert reasons(pc2.compliance_details) == ["BitLocker desactivado", "Firmas de Defender desactualizadas"]
    assert pc2.compliance_checked_at is not None
    # Solo se pide el detalle de los no conformes.
    assert not any("intune-1/deviceCompliancePolicyStates" in c for c in fake.calls)

    fake.devices[1]["complianceState"] = "compliant"
    run = runs.enqueue(db, "intune", "manual", "tester")
    db.commit()
    runs.execute_run(db, run, factory=lambda src, params: IntuneConnector(fake.client()))
    db.refresh(pc2)
    assert pc2.compliance_details == {"policies": []}


def test_sync_continues_without_compliance_permission(db):
    fake = _fake()
    fake.fail = lambda req: (httpx.Response(403, json={"error": {"code": "Forbidden"}})
                             if req.url.path.endswith("/deviceCompliancePolicyStates") else None)
    result = IntuneConnector(fake.client()).extract({}, lambda m: None)
    assert result.complete and any("DeviceManagementConfiguration.Read.All" in w for w in result.warnings)


# --------------------------------------------------------------------------- API
@pytest.fixture()
def api(engine, db, monkeypatch):
    fake = _fake()
    runs.execute_run(db, runs.enqueue(db, "intune", "manual", "tester"),
                     factory=lambda src, params: IntuneConnector(fake.client()))
    monkeypatch.setattr(graph_session, "make_client", fake.client)
    monkeypatch.setattr(graph_session, "configured", lambda: True)
    app = create_app()

    def as_role(role):
        app.dependency_overrides[get_current_user] = lambda: CurrentUser(upn=f"{role}@asserta.test", name=role,
                                                                          role=role)
    as_role("technician")
    client = TestClient(app)
    pc2 = db.execute(select(Device).where(Device.hostname == "PC-002")).scalar_one()
    return client, fake, pc2.id, as_role


def test_list_shows_reasons_and_detail_refreshes(api):
    client, fake, dev_id, _ = api
    items = client.get("/api/devices").json()["items"]
    assert next(i for i in items if i["id"] == dev_id)["compliance_reasons"][0] == "BitLocker desactivado"
    fake.compliance["intune-2"] = [policy("Seguridad Windows", "nonCompliant", (SIGNATURES, "nonCompliant"))]
    body = client.get(f"/api/devices/{dev_id}/compliance", params={"refresh": True}).json()
    assert body["compliance_state"] == "noncompliant" and body["intune_device_id"] == "intune-2"
    assert [s["action"] for s in body["policies"][0]["settings"]] == ["defender_signatures"]
    assert client.get(f"/api/devices/{dev_id}/compliance").json()["policies"] == body["policies"]


def test_intune_action_is_audited_and_restricted(api, db):
    client, fake, dev_id, as_role = api
    r = client.post(f"/api/devices/{dev_id}/intune-actions", json={"action": "sync"})
    assert r.status_code == 202
    assert "POST /v1.0/deviceManagement/managedDevices/intune-2/syncDevice" in fake.calls
    assert db.execute(select(AuditEvent).where(AuditEvent.action == "device.intune_action")).scalar_one()
    assert client.post(f"/api/devices/{dev_id}/intune-actions", json={"action": "wipe"}).status_code == 422
    as_role("auditor")
    assert client.post(f"/api/devices/{dev_id}/intune-actions", json={"action": "sync"}).status_code == 403


def test_missing_graph_permission_returns_clear_403(api):
    client, fake, dev_id, _ = api
    fake.fail = lambda req: httpx.Response(403, json={"error": {"code": "Forbidden"}}) if req.method == "POST" else None
    r = client.post(f"/api/devices/{dev_id}/intune-actions", json={"action": "defender_scan"})
    assert r.status_code == 403 and "PrivilegedOperations" in r.json()["detail"]


def test_manual_device_without_intune_id(api):
    client, _, _, _ = api
    dev = client.post("/api/devices", json={"hostname": "MANUAL-1"}).json()
    assert client.get(f"/api/devices/{dev['id']}/compliance", params={"refresh": True}).status_code == 409
