"""Avisos por correo y desinstalaciones con Intune Remediations (Graph simulado, sin red)."""
from __future__ import annotations

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.connectors.base import ConnectorError
from app.core.security import CurrentUser, get_current_user
from app.db import utcnow
from app.main import create_app
from app.models import DeviceExternalId, RemoteAction, SoftwareProduct, User
from app.services import graph_session, remote_actions, runs
from app.services import uninstall_script as scripts

PANDA = ("Nombre\tEditor\tFecha de instalación\tTamaño\tVersión\n"
         "AnyDesk\tAnyDesk Software GmbH\t10/03/2026\t2 MB\t9.0.10\n"
         "5319275A.WhatsAppDesktop\tWhatsApp Inc.\t10/03/2026\t2 MB\t2.24\n"
         "Google Chrome\tGoogle LLC\t01/02/2026\t100 MB\t129.0.1\n")


class StubGraph:
    """Registra las peticiones; deviceHealthScripts devuelve un id y deviceRunStates lo que se fije en `states`."""

    def __init__(self, fail_on: str | None = None, kind: str = "permission"):
        self.calls: list[tuple] = []
        self.states: list[dict] = []
        self.fail_on, self.kind = fail_on, kind

    def _maybe_fail(self, path):
        if self.fail_on and self.fail_on in path:
            raise ConnectorError("Permisos insuficientes en Graph.", kind=self.kind)

    def post(self, path, json=None):
        self.calls.append(("POST", path, json))
        self._maybe_fail(path)
        return {"id": "script-1"} if path.endswith("/deviceHealthScripts") else {}

    def patch(self, path, json=None):
        self.calls.append(("PATCH", path, json))
        return {}

    def get(self, path, params=None):
        self.calls.append(("GET", path, params))
        return {"value": self.states}

    def paths(self, method=None):
        return [c[1] for c in self.calls if method in (None, c[0])]


@pytest.fixture()
def app(engine):
    a = create_app()
    a.dependency_overrides[get_current_user] = lambda: CurrentUser(upn="tecnico@asserta.test", name="T", role="admin")
    return a


@pytest.fixture()
def client(app):
    return TestClient(app)


@pytest.fixture()
def graph(monkeypatch):
    stub = StubGraph()
    monkeypatch.setattr(graph_session, "configured", lambda: True)
    monkeypatch.setattr(graph_session, "make_client", lambda: stub)
    return stub


def _device(client, db, name: str, upn: str | None, intune: bool = True) -> int:
    body = {"hostname": name, **({"primary_user_upn": upn} if upn else {})}
    dev = client.post("/api/devices", json=body).json()
    client.post("/api/runs/upload", data={"source": "panda", "device_id": str(dev["id"])},
                files={"file": ("export.txt", PANDA.encode("utf-8"), "text/plain")})
    while (run := runs.claim_next(db)) is not None:
        runs.execute_run(db, run)
    if intune:
        db.add(DeviceExternalId(device_id=dev["id"], source="intune", id_type="intune_device_id", value=f"intune-{name}"))
        db.commit()
    return dev["id"]


def _product(db, name: str) -> SoftwareProduct:
    return db.execute(select(SoftwareProduct).where(SoftwareProduct.name == name)).scalar_one()


@pytest.fixture()
def fleet(client, db):
    """Dos equipos con usuario (uno de ellos con dos), uno sin usuario y uno fuera de Intune."""
    ids = {"PC-1": _device(client, db, "PC-1", "laura.perez@asserta.test"),
           "PC-2": _device(client, db, "PC-2", "laura.perez@asserta.test"),
           "PC-3": _device(client, db, "PC-3", None),
           "PC-4": _device(client, db, "PC-4", "ivan@asserta.test", intune=False)}
    for u in db.execute(select(User)).scalars():
        if u.upn.startswith("laura"):
            u.display_name = "Laura Pérez"
    anydesk, whatsapp = _product(db, "AnyDesk"), _product(db, "5319275A.WhatsAppDesktop")
    anydesk.notes = "[Política] Motivo: Acceso remoto no aprobado · Alternativa: Asistencia rápida de Windows"
    db.commit()
    client.post("/api/software/bulk-update", json={"product_ids": [anydesk.id, whatsapp.id],
                                                    "authorization_status": "unauthorized"})
    client.put("/api/settings/notify", json={"sender": "it@asserta.test", "cc": "", "subject": "Aviso para {nombre}",
                                             "body": "Hola {nombre}, en {equipo}:\n{programas}"})
    return {**ids, "anydesk": anydesk.id, "whatsapp": whatsapp.id}


# --------------------------------------------------------------------------- generador de scripts
def test_script_builder_methods_and_safeguards(db):
    p = SoftwareProduct(id=7, name="AnyDesk", name_key="anydesk", authorization_status="unauthorized",
                        category="application", is_relevant=True)
    built = scripts.build(p, ["AnyDesk", "O'Brien Tool"])
    assert built["method"] == "Registro (MSI o EXE)" and "'O''Brien Tool'" in built["detection"]
    assert "msiexec.exe" in built["remediation"] and "QuietUninstallString" in built["remediation"]
    appx = SoftwareProduct(id=8, name="5319275A.WhatsAppDesktop", name_key="w", authorization_status="unauthorized",
                           category="application", is_relevant=True)
    assert scripts.build(appx, [])["method"] == "AppX/MSIX"
    assert scripts.build(appx, [])["hash"] == scripts.build(appx, [])["hash"]
    for name, status, err in (("AnyDesk", "conditional", "No autorizado"), ("Microsoft Edge", "unauthorized", "base"),
                              ("Intune Management Extension", "unauthorized", "base")):
        with pytest.raises(scripts.NotUninstallable, match=err):
            scripts.build(SoftwareProduct(id=9, name=name, name_key="x", authorization_status=status,
                                          category="application", is_relevant=True), [])
    # «WhatsApp for Windows» no es Windows: sí se puede desinstalar.
    scripts.check(SoftwareProduct(id=10, name="WhatsApp for Windows", name_key="x", authorization_status="unauthorized",
                                  category="application", is_relevant=True))
    assert [scripts.interpret(o) for o in ("OK: x", "OK: a | MANUAL: b", "OK: a | FALLO: b")] == \
        ["succeeded", "manual_required", "failed"]


# --------------------------------------------------------------------------- avisos
def test_notify_preview_and_send_one_mail_per_person(client, db, graph, fleet):
    prev = client.post("/api/notifications/preview", json={"product_id": fleet["anydesk"]}).json()
    assert prev["no_user"] == ["PC-3"] and {r["upn"] for r in prev["recipients"]} == {"laura.perez@asserta.test",
                                                                                    "ivan@asserta.test"}
    assert graph.calls == []  # la vista previa no envía nada
    laura = next(r for r in prev["recipients"] if r["upn"].startswith("laura"))
    assert laura["subject"] == "Aviso para Laura" and "PC-1, PC-2" in laura["body"]
    assert "Asistencia rápida de Windows" in laura["body"]

    r = client.post("/api/notifications/send", json={"device_ids": [fleet["PC-1"], fleet["PC-2"], fleet["PC-3"]]})
    assert r.status_code == 200 and r.json()["sent"] == 1 and r.json()["no_user"] == ["PC-3"]
    (method, path, body), = graph.calls
    assert path == "/v1.0/users/it@asserta.test/sendMail"
    text = body["message"]["body"]["content"]
    assert "AnyDesk" in text and "WhatsAppDesktop" in text  # todos sus programas en un único correo
    notes = db.execute(select(RemoteAction).where(RemoteAction.kind == "notify")).scalars().all()
    assert len(notes) == 4 and {n.recipient for n in notes} == {"laura.perez@asserta.test"}
    alerts = client.get("/api/alerts", params={"type": "unauthorized_software"}).json()["items"]
    pc1 = next(a for a in alerts if a["device_id"] == fleet["PC-1"])
    assert pc1["last_action"]["kind"] == "notify" and pc1["last_action"]["status"] == "sent"


def test_notify_errors(client, db, graph, fleet, monkeypatch):
    client.put("/api/settings/notify", json={"sender": "", "cc": "", "subject": "Aviso", "body": "Hola {nombre} texto"})
    assert client.post("/api/notifications/send", json={"product_id": fleet["anydesk"]}).status_code == 409
    client.put("/api/settings/notify", json={"sender": "it@asserta.test", "cc": "", "subject": "Aviso",
                                             "body": "Hola {nombre} texto"})
    denied = StubGraph(fail_on="sendMail")
    monkeypatch.setattr(graph_session, "make_client", lambda: denied)
    r = client.post("/api/notifications/send", json={"product_id": fleet["anydesk"]})
    assert r.status_code == 403 and "Mail.Send.Shared" in r.json()["detail"]
    assert db.execute(select(RemoteAction)).first() is None
    assert client.post("/api/notifications/preview", json={}).status_code == 422


# --------------------------------------------------------------------------- desinstalaciones
def test_uninstall_preview_launch_and_reuse_script(client, db, graph, fleet):
    prev = client.post("/api/uninstalls/preview", json={"product_id": fleet["anydesk"]}).json()
    assert prev["blocked"] is None and {d["name"] for d in prev["devices"]} == {"PC-1", "PC-2", "PC-3"}
    assert prev["skipped"] == [{"id": fleet["PC-4"], "name": "PC-4", "reason": "No está gestionado por Intune"}]
    assert graph.calls == [] and db.execute(select(RemoteAction)).first() is None

    r = client.post("/api/uninstalls", json={"product_id": fleet["anydesk"], "reason": "Política de software",
                                             "device_ids": [fleet["PC-1"], fleet["PC-4"]], "notify_first": True})
    assert r.status_code == 200 and r.json()["launched"] == 1 and r.json()["notified"]["sent"] == 1
    assert graph.paths("POST") == ["/v1.0/users/it@asserta.test/sendMail", "/beta/deviceManagement/deviceHealthScripts",
                                   "/beta/deviceManagement/managedDevices/intune-PC-1/initiateOnDemandProactiveRemediation"]
    created = graph.calls[1][2]
    assert created["runAsAccount"] == "system" and created["remediationScriptContent"]
    # Otra desinstalación del mismo producto reutiliza el script.
    graph.calls.clear()
    client.post("/api/uninstalls", json={"product_id": fleet["anydesk"], "reason": "Política", "device_ids": [fleet["PC-2"]],
                                         "notify_first": False})
    assert graph.paths("POST") == ["/beta/deviceManagement/managedDevices/intune-PC-2/initiateOnDemandProactiveRemediation"]
    listed = client.get("/api/remote-actions", params={"kind": "uninstall"}).json()
    assert listed["total"] == 2 and {a["status"] for a in listed["items"]} == {"sent"}


def test_uninstall_refuses_and_reports_permissions(client, db, graph, fleet, monkeypatch):
    chrome = _product(db, "Google Chrome")
    r = client.post("/api/uninstalls", json={"product_id": chrome.id, "reason": "x" * 5, "device_ids": [fleet["PC-1"]]})
    assert r.status_code == 422 and "No autorizado" in r.json()["detail"]
    assert client.post("/api/uninstalls/preview", json={"product_id": chrome.id}).json()["blocked"]
    denied = StubGraph(fail_on="deviceHealthScripts")
    monkeypatch.setattr(graph_session, "make_client", lambda: denied)
    r = client.post("/api/uninstalls", json={"product_id": fleet["anydesk"], "reason": "Política",
                                             "device_ids": [fleet["PC-1"]], "notify_first": False})
    assert r.status_code == 403 and "ReadWrite.All" in r.json()["detail"]
    assert db.execute(select(RemoteAction)).first() is None


def test_worker_poll_maps_intune_results(client, db, graph, fleet):
    client.post("/api/uninstalls", json={"product_id": fleet["anydesk"], "reason": "Política", "notify_first": False,
                                         "device_ids": [fleet["PC-1"], fleet["PC-2"], fleet["PC-3"]]})
    now = utcnow().isoformat() + "Z"
    old = (utcnow() - timedelta(days=3)).isoformat() + "Z"
    graph.states = [
        {"managedDevice": {"id": "intune-PC-1"}, "detectionState": "fail", "remediationState": "success",
         "remediationScriptOutput": "OK: AnyDesk 9.0.10 (silencioso)", "lastStateUpdateDateTime": now},
        {"managedDevice": {"id": "intune-PC-2"}, "detectionState": "fail", "remediationState": "success",
         "remediationScriptOutput": "MANUAL: AnyDesk no tiene desinstalación silenciosa", "lastStateUpdateDateTime": now},
        # Resultado de una ejecución anterior: se ignora.
        {"managedDevice": {"id": "intune-PC-3"}, "detectionState": "fail", "remediationState": "remediationFailed",
         "lastStateUpdateDateTime": old},
    ]
    graph.calls.clear()
    summary = remote_actions.poll(db, graph)
    db.commit()
    status = {a.device.display_name: a.status for a in db.execute(select(RemoteAction)).scalars()}
    assert status == {"PC-1": "succeeded", "PC-2": "manual_required", "PC-3": "sent"}
    assert summary["finished"] == 2
    assert "/v1.0/deviceManagement/managedDevices/intune-PC-1/syncDevice" in graph.paths("POST")
    # Sin resultado en 24 horas: caduca.
    pending = db.execute(select(RemoteAction).where(RemoteAction.status == "sent")).scalar_one()
    pending.requested_at = utcnow() - timedelta(hours=25)
    db.commit()
    remote_actions.poll(db, graph)
    db.commit()
    db.refresh(pending)
    assert pending.status == "expired"
    assert client.post(f"/api/remote-actions/{pending.id}/retry").status_code == 200

