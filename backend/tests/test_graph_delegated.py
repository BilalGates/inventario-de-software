import json

import httpx
import jwt
import pytest

from app.connectors.base import ConnectorError
from app.connectors.graph import GraphClient
from app.connectors.graph_delegated import (
    MAIL_SCOPE,
    READ_SCOPE,
    SCOPE,
    DelegatedTokenProvider,
    DeviceCodeLogin,
    EncryptedSettingStore,
)

KEY = "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY="  # 32 bytes en base64, solo para pruebas
ID_TOKEN = jwt.encode({"preferred_username": "it@asserta.test", "tid": "tenant-1"}, "k", algorithm="HS256")


def _http(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def _store(name: str = "secret.graph.session") -> EncryptedSettingStore:
    return EncryptedSettingStore(name, KEY)


def test_device_code_flow_saves_session(engine):
    calls = {"token": 0}

    def handler(req: httpx.Request):
        if req.url.path.endswith("/devicecode"):
            return httpx.Response(200, json={"device_code": "dc", "user_code": "ABC123", "expires_in": 900,
                                             "interval": 0, "verification_uri": "https://microsoft.com/devicelogin"})
        calls["token"] += 1
        if calls["token"] == 1:
            return httpx.Response(400, json={"error": "authorization_pending"})
        return httpx.Response(200, json={"access_token": "at", "refresh_token": "rt", "id_token": ID_TOKEN})

    store = _store()
    login = DeviceCodeLogin(store, _http(handler))
    assert login.poll() == {"status": "idle"}
    assert login.start()["user_code"] == "ABC123"
    assert login.poll()["status"] == "pending"
    assert login.poll() == {"status": "connected", "account": "it@asserta.test"}
    saved = store.load()
    assert saved["refresh_token"] == "rt" and saved["tenant_id"] == "tenant-1"
    assert login.poll() == {"status": "idle"}


def test_device_code_rejected(engine):
    def handler(req):
        if req.url.path.endswith("/devicecode"):
            return httpx.Response(200, json={"device_code": "dc", "user_code": "X", "expires_in": 900, "interval": 0,
                                             "verification_uri": "u"})
        return httpx.Response(400, json={"error": "access_denied"})

    login = DeviceCodeLogin(_store(), _http(handler))
    login.start()
    assert login.poll()["status"] == "error"
    assert not _store().exists()


def test_provider_refreshes_and_rotates_refresh_token(engine):
    store = _store()
    store.save({"refresh_token": "rt-1", "tenant_id": "tenant-1", "account": "it@asserta.test"})
    seen = []

    def handler(req: httpx.Request):
        if "login.microsoftonline.com" in req.url.host:
            body = dict(x.split("=") for x in req.content.decode().split("&"))
            seen.append((req.url.path, body["refresh_token"]))
            return httpx.Response(200, json={"access_token": "at-2", "refresh_token": "rt-2", "expires_in": 3600})
        assert req.headers["Authorization"] == "Bearer at-2"
        return httpx.Response(200, json={"value": [{"id": "d1"}]})

    http = _http(handler)
    client = GraphClient("", "", http=http, token_provider=DelegatedTokenProvider(store, http))
    assert list(client.paginate("/v1.0/deviceManagement/managedDevices")) == [{"id": "d1"}]
    assert seen == [("/tenant-1/oauth2/v2.0/token", "rt-1")]
    assert store.load()["refresh_token"] == "rt-2"


def test_provider_expired_session(engine):
    store = _store()
    store.save({"refresh_token": "rt"})
    provider = DelegatedTokenProvider(store, _http(lambda req: httpx.Response(400, json={"error": "invalid_grant"})))
    with pytest.raises(ConnectorError, match="caducado"):
        provider(True)


def _scopes(req: httpx.Request) -> str:
    from urllib.parse import parse_qs
    return parse_qs(req.content.decode())["scope"][0]


def test_refresh_never_asks_for_default_scope(engine):
    store = _store()
    store.save({"refresh_token": "rt"})
    asked = []

    def handler(req):
        asked.append(_scopes(req))
        return httpx.Response(200, json={"access_token": "at", "expires_in": 3600})

    DelegatedTokenProvider(store, _http(handler))(True)
    assert asked == [SCOPE] and ".default" not in asked[0]


def test_old_session_without_consent_falls_back_one_level_at_a_time(engine):
    store = _store()
    store.save({"refresh_token": "rt"})
    asked = []
    refused = {SCOPE}

    def handler(req):
        asked.append(_scopes(req))
        if _scopes(req) in refused:
            return httpx.Response(400, json={"error": "invalid_grant", "error_codes": [65001]})
        return httpx.Response(200, json={"access_token": "at", "expires_in": 3600})

    # Sin consentimiento de administrador: baja a «mail» (avisos por correo) y se queda ahí.
    assert DelegatedTokenProvider(store, _http(handler))(True) == "at"
    assert asked == [SCOPE, MAIL_SCOPE] and store.load()["scopes"] == "mail"
    asked.clear()
    DelegatedTokenProvider(store, _http(handler))(True)
    assert asked == [MAIL_SCOPE]
    # Si tampoco hay consentimiento para el correo: solo lectura.
    refused.add(MAIL_SCOPE)
    asked.clear()
    DelegatedTokenProvider(store, _http(handler))(True)
    assert asked == [MAIL_SCOPE, READ_SCOPE] and store.load()["scopes"] == "read"
    asked.clear()
    DelegatedTokenProvider(store, _http(handler))(True)
    assert asked == [READ_SCOPE]


def test_provider_without_session(engine):
    with pytest.raises(ConnectorError) as exc:
        DelegatedTokenProvider(_store("secret.vacia"))(False)
    assert exc.value.kind == "config"


def test_graph_client_still_requires_credentials_without_provider():
    with pytest.raises(ConnectorError):
        GraphClient("", "")


# --------------------------------------------------------------------------- nube (sesión en la base)


def test_encrypted_store_in_database_is_not_plaintext(engine, db):
    from app.connectors.graph_delegated import EncryptedSettingStore
    from app.models import AppSetting

    store = EncryptedSettingStore("secret.graph.session", KEY)
    store.save({"refresh_token": "secreto-rt", "account": "it@asserta.test"})
    raw = db.get(AppSetting, "secret.graph.session").value
    assert "secreto-rt" not in json.dumps(raw)
    assert store.load() == {"refresh_token": "secreto-rt", "account": "it@asserta.test"}
    other = EncryptedSettingStore("secret.graph.session", "ZmVkY2JhOTg3NjU0MzIxMGZlZGNiYTk4NzY1NDMyMTA=")
    assert other.load() is None  # otra clave: no se descifra
    store.delete()
    assert store.load() is None and not store.exists()


def test_encryption_key_must_be_32_bytes():
    from app.connectors.graph_delegated import EncryptedSettingStore

    with pytest.raises(ValueError, match="32 bytes"):
        EncryptedSettingStore("x", "corta")


def test_device_code_login_survives_another_instance(engine):
    """En Vercel, «Conectar» y cada comprobación pueden ir a instancias distintas."""
    from app.connectors.graph_delegated import EncryptedSettingStore

    def handler(req: httpx.Request):
        if req.url.path.endswith("/devicecode"):
            return httpx.Response(200, json={"device_code": "dc", "user_code": "ABC123", "expires_in": 900,
                                             "interval": 0, "verification_uri": "https://microsoft.com/devicelogin"})
        return httpx.Response(200, json={"access_token": "at", "refresh_token": "rt", "id_token": ID_TOKEN})

    def instance():
        return DeviceCodeLogin(EncryptedSettingStore("secret.graph.session", KEY), _http(handler),
                               pending_store=EncryptedSettingStore("secret.graph.device_login", KEY))

    assert instance().start()["user_code"] == "ABC123"
    assert instance().poll() == {"status": "connected", "account": "it@asserta.test"}
    assert instance().poll() == {"status": "idle"}  # el pendiente se borró
    saved = EncryptedSettingStore("secret.graph.session", KEY).load()
    assert saved["refresh_token"] == "rt" and saved["tenant_id"] == "tenant-1"


def test_worker_uses_cloud_session_and_saves_rotated_token(engine, monkeypatch):
    from app.core.config import get_settings
    from app.models import InventorySource
    from app.services import graph_session, runs

    monkeypatch.setattr(get_settings(), "token_encryption_key", KEY)
    assert graph_session.configured() is False
    graph_session.token_store().save({"refresh_token": "rt-1", "tenant_id": "tenant-1"})
    assert graph_session.configured() is True
    connector = runs.default_connector_factory(InventorySource(code="intune", config={}), {})
    provider = connector.client._token_provider
    provider.http = _http(lambda req: httpx.Response(200, json={"access_token": "at", "refresh_token": "rt-2",
                                                                 "expires_in": 3600}))
    assert provider() == "at"
    assert graph_session.saved_session()["refresh_token"] == "rt-2"  # rotado y guardado para la próxima


def test_connect_asks_read_only_by_default_and_full_on_demand(engine):
    asked = []

    def handler(req):
        if req.url.path.endswith("/devicecode"):
            asked.append(_scopes(req))
            return httpx.Response(200, json={"device_code": "dc", "user_code": "X", "expires_in": 900,
                                             "interval": 0, "verification_uri": "https://microsoft.com/devicelogin"})
        return httpx.Response(200, json={"access_token": "at", "refresh_token": "rt", "id_token": ID_TOKEN})

    store = _store()
    login = DeviceCodeLogin(store, _http(handler))
    login.start()
    login.poll()
    assert asked == [READ_SCOPE] and store.load()["scopes"] == "read"
    login.start(full=True)
    login.poll()
    assert asked[-1] == SCOPE and store.load()["scopes"] == "full"


def test_denied_full_consent_keeps_previous_session(engine):
    def handler(req):
        if req.url.path.endswith("/devicecode"):
            return httpx.Response(200, json={"device_code": "dc", "user_code": "X", "expires_in": 900,
                                             "interval": 0, "verification_uri": "https://microsoft.com/devicelogin"})
        return httpx.Response(400, json={"error": "access_denied"})

    store = _store()
    store.save({"refresh_token": "rt-lectura", "scopes": "read"})
    login = DeviceCodeLogin(store, _http(handler))
    login.start(full=True)
    assert login.poll()["status"] == "error"
    assert store.load()["refresh_token"] == "rt-lectura"
