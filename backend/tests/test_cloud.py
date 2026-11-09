"""Despliegue en la nube: URL de PostgreSQL, aviso al worker de GitHub Actions y copia de la base."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.copy_database import check, copy, verify
from app.core.config import get_settings
from app.core.security import CurrentUser, get_current_user
from app.db import Base, make_engine, normalize_url
from app.main import create_app
from app.models import Department, Device
from app.services import audit, dispatch


def test_normalize_url_uses_psycopg():
    assert normalize_url("postgres://u:p@h:6543/postgres") == "postgresql+psycopg://u:p@h:6543/postgres"
    assert normalize_url("postgresql://u:p@h/db") == "postgresql+psycopg://u:p@h/db"
    assert normalize_url("postgresql+psycopg://x") == "postgresql+psycopg://x"
    assert normalize_url("sqlite:///a.db") == "sqlite:///a.db"


@pytest.fixture()
def dispatch_on(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "worker_dispatch_token", "tok")
    monkeypatch.setattr(s, "worker_dispatch_repo", "org/repo")
    calls = []

    def fake_post(url, json, timeout, headers):  # noqa: A002 - misma firma que httpx.post
        calls.append((url, json, headers["Authorization"]))
        return type("R", (), {"status_code": 204, "text": ""})()

    monkeypatch.setattr(dispatch.httpx, "post", fake_post)
    return calls


def test_wake_worker_without_token_does_nothing(monkeypatch):
    monkeypatch.setattr(get_settings(), "worker_dispatch_token", "")
    assert dispatch.wake_worker() is False


def test_wake_worker_dispatches_workflow(dispatch_on):
    assert dispatch.wake_worker(wait=True) is True
    assert dispatch_on == [("https://api.github.com/repos/org/repo/actions/workflows/worker.yml/dispatches",
                            {"ref": "main"}, "Bearer tok")]


def test_upload_wakes_worker(engine, dispatch_on, monkeypatch):
    monkeypatch.setattr(get_settings(), "serverless", True)  # en Vercel se espera a la llamada
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(upn="t@asserta.test", name="t", role="technician")
    r = TestClient(app).post("/api/runs/upload", data={"source": "panda"},
                             files={"file": ("PC-01.txt", b"Nombre\tEditor\nZoom\tZoom\n", "text/plain")})
    assert r.status_code == 202
    assert len(dispatch_on) == 1


def _sqlite(path) -> object:
    eng = make_engine(f"sqlite:///{path}")
    Base.metadata.create_all(eng)
    with eng.begin() as c:
        c.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"))
        c.execute(text("INSERT INTO alembic_version VALUES ('defceba439ac')"))
    return eng


def test_copy_database_keeps_ids_links_and_audit_chain(tmp_path):
    src, dst = _sqlite(tmp_path / "origen.db"), _sqlite(tmp_path / "destino.db")
    with Session(src) as db:
        dept = Department(code="SIL", name="Silicon")
        db.add(dept)
        db.flush()
        db.add_all([Device(hostname="PC-01", department_id=dept.id), Device(hostname="PC-02")])
        audit.record(db, "t@asserta.test", "department.create", "department", dept.id, "Silicon")
        audit.record(db, "t@asserta.test", "device.create", "device", 1, "PC-01")
        db.commit()
    assert check(src, dst) == []
    copied = copy(src, dst, log=lambda *_: None)
    assert copied["devices"] == 2 and copied["audit_events"] == 2
    assert verify(src, dst) == []
    with Session(dst) as db:
        pc = db.execute(select(Device).where(Device.hostname == "PC-01")).scalar_one()
        assert pc.department.name == "Silicon"
    # Un destino con datos no se sobrescribe.
    assert any("ya tiene datos" in p for p in check(src, dst))


def test_copy_database_refuses_target_without_schema(tmp_path):
    src = _sqlite(tmp_path / "origen.db")
    empty = make_engine(f"sqlite:///{tmp_path / 'vacia.db'}")
    assert any("alembic upgrade head" in p for p in check(src, empty))


def test_vercel_requirements_match_backend_versions():
    """El requirements.txt de la raíz (Vercel) debe usar las mismas versiones que el backend."""
    from pathlib import Path

    def pins(path: Path) -> dict[str, str]:
        out = {}
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.split("#", 1)[0].split(";", 1)[0].strip()
            if "==" in line:
                name, version = line.split("==", 1)
                out[name.split("[", 1)[0].lower()] = version.strip()
        return out

    root = Path(__file__).resolve().parents[2]
    vercel, backend = pins(root / "requirements.txt"), pins(root / "backend" / "requirements.txt")
    lines = [ln.strip() for ln in (root / "requirements.txt").read_text(encoding="utf-8").splitlines()]
    assert not [ln for ln in lines if ln.startswith("-")], "Vercel no admite opciones como -r en requirements.txt"
    assert vercel and all(backend.get(k) == v for k, v in vercel.items()), (vercel, backend)
    needed = {"fastapi", "sqlalchemy", "pydantic", "pydantic-settings", "httpx", "pyjwt", "psycopg", "openpyxl",
              "python-multipart"}
    assert needed <= set(vercel)


def test_vercel_refuses_to_start_without_login(monkeypatch):
    """En Vercel la URL es pública: sin Entra cualquiera entraría como administrador."""
    from pydantic import ValidationError

    from app.core.config import Settings

    monkeypatch.setenv("VERCEL", "1")
    with pytest.raises(ValidationError, match="INV_AUTH_MODE=entra"):
        Settings(auth_mode="dev", environment="development")


def test_vercel_with_entra_starts(monkeypatch):
    from app.core.config import Settings

    monkeypatch.setenv("VERCEL", "1")
    s = Settings(auth_mode="entra", environment="production", entra_tenant_id="t", entra_api_client_id="a",
                 database_url="postgresql://u:p@h:6543/postgres")
    assert s.serverless is True


def test_copy_database_replaces_users_created_by_login(tmp_path):
    """Entrar en la web antes de copiar crea una fila en «users»: no debe bloquear la copia."""
    from app.models import User

    src, dst = _sqlite(tmp_path / "origen.db"), _sqlite(tmp_path / "destino.db")
    with Session(src) as db:
        db.add_all([User(upn="bilal@asserta.net", display_name="Bilal", source="entra", role="admin"),
                    User(upn="elena@asserta.net", display_name="Elena", source="entra", role="auditor")])
        db.commit()
    with Session(dst) as db:  # lo que deja el primer inicio de sesión en Supabase
        db.add(User(upn="bilal@asserta.net", display_name="Bilal El Arbi", source="entra", role="admin"))
        db.commit()
    assert check(src, dst) == []
    copy(src, dst, log=lambda *_: None)
    assert verify(src, dst) == []
    with Session(dst) as db:
        assert sorted(db.execute(select(User.upn)).scalars()) == ["bilal@asserta.net", "elena@asserta.net"]


def test_copy_database_reset_clears_worker_leftovers_but_never_real_inventory(tmp_path):
    """El worker ejecutado antes de copiar deja ejecuciones y auditoría: --reset las borra."""
    from app.models import AppSetting, AuditEvent

    src, dst = _sqlite(tmp_path / "origen.db"), _sqlite(tmp_path / "destino.db")
    with Session(src) as db:
        db.add(Device(hostname="PC-01"))
        audit.record(db, "t@asserta.test", "device.create", "device", 1, "PC-01")
        db.commit()
    with Session(dst) as db:  # restos del worker sobre la base vacía
        audit.record(db, "system:scheduler", "run.enqueue", "inventory_run", 1, "intune (schedule)")
        db.add(AppSetting(key="worker.heartbeat", value={"at": "2026-11-09T10:00:00"}))
        db.commit()
    assert any("--reset" in p for p in check(src, dst))
    assert check(src, dst, reset=True) == []
    copy(src, dst, log=lambda *_: None, reset=True)
    assert verify(src, dst) == []  # incluye la cadena de auditoría: solo quedan los eventos del origen
    with Session(dst) as db:
        assert [e.action for e in db.execute(select(AuditEvent)).scalars()] == ["device.create"]
    # Con inventario real en el destino, --reset se niega.
    assert any("inventario real" in p for p in check(src, dst, reset=True))


def test_copy_database_overwrite_replaces_real_inventory_after_confirmation(tmp_path, monkeypatch):
    from app.copy_database import main

    src, dst = _sqlite(tmp_path / "origen.db"), _sqlite(tmp_path / "destino.db")
    with Session(src) as db:
        db.add_all([Device(hostname="PC-01"), Device(hostname="PC-02")])
        db.commit()
    with Session(dst) as db:  # una sincronización hecha en la nube antes de copiar
        db.add(Device(hostname="PC-NUBE"))
        db.commit()
    args = ["--source", f"sqlite:///{tmp_path / 'origen.db'}", "--target", f"sqlite:///{tmp_path / 'destino.db'}"]
    assert check(src, dst, reset=True) and check(src, dst, reset=True, overwrite=True) == []
    monkeypatch.setattr("builtins.input", lambda *_: "no")
    assert main([*args, "--overwrite"]) == 1  # sin confirmar no toca nada
    with Session(dst) as db:
        assert [d.hostname for d in db.execute(select(Device)).scalars()] == ["PC-NUBE"]
    monkeypatch.setattr("builtins.input", lambda *_: "SUSTITUIR")
    assert main([*args, "--overwrite"]) == 0
    with Session(dst) as db:
        assert sorted(d.hostname for d in db.execute(select(Device)).scalars()) == ["PC-01", "PC-02"]
