"""Fotos de perfil: descarga en caché, usuarios sin foto, falta de permiso y respuesta para la web."""
from __future__ import annotations

from datetime import timedelta

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.connectors.base import ConnectorError
from app.connectors.graph import GraphClient
from app.core.security import CurrentUser, get_current_user
from app.db import utcnow
from app.main import create_app
from app.models import User
from app.services import graph_session, photos

JPEG = b"\xff\xd8\xff\xe0fake-jpeg"


class StubPhotos:
    def __init__(self, have: dict[str, bytes], deny: bool = False):
        self.have, self.deny, self.asked = have, deny, []

    def get_bytes(self, path):
        self.asked.append(path)
        if self.deny:
            raise ConnectorError("Permisos insuficientes", kind="permission")
        upn = path.split("/users/")[1].split("/")[0].replace("%40", "@")
        return (self.have[upn], "image/jpeg") if upn in self.have else None


@pytest.fixture()
def users(db):
    for upn in ("ana@asserta.test", "luis@asserta.test", "sin-correo"):
        db.add(User(upn=upn, display_name=upn))
    db.commit()


def test_refresh_stores_photos_and_marks_users_without_one(db, users):
    stub = StubPhotos({"ana@asserta.test": JPEG})
    result = photos.refresh(db, stub)
    db.commit()
    assert result == {"updated": 2, "found": 1}  # «sin-correo» no es una cuenta de Microsoft 365
    assert photos.all_photos(db) == {"ana@asserta.test": "data:image/jpeg;base64,/9j/4GZha2UtanBlZw=="}
    # Revisadas hace poco: no se vuelven a pedir hasta dentro de una semana.
    stub.asked.clear()
    photos.refresh(db, stub)
    assert stub.asked == []
    for u in db.execute(select(User)).scalars():
        u.photo_checked_at = utcnow() - timedelta(days=8) if u.photo_checked_at else None
    db.commit()
    photos.refresh(db, stub)
    assert len(stub.asked) == 2


def test_without_permission_stops_and_waits_a_day(db, users):
    stub = StubPhotos({}, deny=True)
    assert photos.refresh(db, stub)["skipped"] == "permission"
    assert len(stub.asked) == 1
    stub.asked.clear()
    assert photos.refresh(db, stub) == {"skipped": "permission"} and stub.asked == []
    assert db.execute(select(User).where(User.photo_checked_at.is_not(None))).first() is None


def test_graph_client_get_bytes():
    def handler(req: httpx.Request):
        if "login.microsoftonline.com" in req.url.host:
            return httpx.Response(200, json={"access_token": "t", "expires_in": 3600})
        if "ana" in str(req.url):
            return httpx.Response(200, content=JPEG, headers={"content-type": "image/jpeg"})
        if "luis" in str(req.url):
            return httpx.Response(404, json={"error": {"code": "ImageNotFound"}})
        return httpx.Response(403, json={"error": {"code": "Authorization_RequestDenied"}})

    client = GraphClient("tenant", "client", "secret", http=httpx.Client(transport=httpx.MockTransport(handler)))
    assert client.get_bytes("/v1.0/users/ana@x/photos/96x96/$value") == (JPEG, "image/jpeg")
    assert client.get_bytes("/v1.0/users/luis@x/photos/96x96/$value") is None
    with pytest.raises(ConnectorError) as err:
        client.get_bytes("/v1.0/users/otro@x/photos/96x96/$value")
    assert err.value.kind == "permission"


def test_api_photos_and_manual_refresh(engine, db, users, monkeypatch):
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(upn="t@asserta.test", name="T", role="technician")
    client = TestClient(app)
    monkeypatch.setattr(graph_session, "configured", lambda: True)
    monkeypatch.setattr(graph_session, "make_client", lambda: StubPhotos({"luis@asserta.test": JPEG}))
    assert client.get("/api/users/photos").json() == {}
    r = client.post("/api/users/photos/refresh")
    assert r.status_code == 200 and r.json()["found"] == 1
    got = client.get("/api/users/photos")
    assert list(got.json()) == ["luis@asserta.test"] and "private" in got.headers["cache-control"]
    monkeypatch.setattr(graph_session, "make_client", lambda: StubPhotos({}, deny=True))
    for u in db.execute(select(User)).scalars():
        u.photo_checked_at = None
    db.commit()
    r = client.post("/api/users/photos/refresh")
    assert r.status_code == 403 and "ProfilePhoto.Read.All" in r.json()["detail"]
