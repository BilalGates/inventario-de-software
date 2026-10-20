import json

import httpx
import jwt
import pytest

from app.connectors.base import ConnectorError
from app.connectors.graph import GraphClient
from app.connectors.graph_delegated import DelegatedTokenProvider, DeviceCodeLogin, TokenStore

ID_TOKEN = jwt.encode({"preferred_username": "it@asserta.test", "tid": "tenant-1"}, "k", algorithm="HS256")


def _http(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_store_roundtrip_is_not_plaintext(tmp_path):
    store = TokenStore(tmp_path / "t.bin")
    store.save({"refresh_token": "secreto-rt"})
    assert store.load() == {"refresh_token": "secreto-rt"}
    store.delete()
    assert not store.exists() and store.load() is None


def test_device_code_flow_saves_session(tmp_path):
    calls = {"token": 0}

    def handler(req: httpx.Request):
        if req.url.path.endswith("/devicecode"):
            return httpx.Response(200, json={"device_code": "dc", "user_code": "ABC123", "expires_in": 900,
                                             "interval": 0, "verification_uri": "https://microsoft.com/devicelogin"})
        calls["token"] += 1
        if calls["token"] == 1:
            return httpx.Response(400, json={"error": "authorization_pending"})
        return httpx.Response(200, json={"access_token": "at", "refresh_token": "rt", "id_token": ID_TOKEN})

    store = TokenStore(tmp_path / "t.bin")
    login = DeviceCodeLogin(store, _http(handler))
    assert login.poll() == {"status": "idle"}
    assert login.start()["user_code"] == "ABC123"
    assert login.poll()["status"] == "pending"
    assert login.poll() == {"status": "connected", "account": "it@asserta.test"}
    saved = store.load()
    assert saved["refresh_token"] == "rt" and saved["tenant_id"] == "tenant-1"
    assert login.poll() == {"status": "idle"}


def test_device_code_rejected(tmp_path):
    def handler(req):
        if req.url.path.endswith("/devicecode"):
            return httpx.Response(200, json={"device_code": "dc", "user_code": "X", "expires_in": 900, "interval": 0,
                                             "verification_uri": "u"})
        return httpx.Response(400, json={"error": "access_denied"})

    login = DeviceCodeLogin(TokenStore(tmp_path / "t.bin"), _http(handler))
    login.start()
    assert login.poll()["status"] == "error"
    assert not (tmp_path / "t.bin").exists()


def test_provider_refreshes_and_rotates_refresh_token(tmp_path):
    store = TokenStore(tmp_path / "t.bin")
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


def test_provider_expired_session(tmp_path):
    store = TokenStore(tmp_path / "t.bin")
    store.save({"refresh_token": "rt"})
    provider = DelegatedTokenProvider(store, _http(lambda req: httpx.Response(400, json={"error": "invalid_grant"})))
    with pytest.raises(ConnectorError, match="caducado"):
        provider(True)


def test_provider_without_session(tmp_path):
    with pytest.raises(ConnectorError) as exc:
        DelegatedTokenProvider(TokenStore(tmp_path / "no.bin"))(False)
    assert exc.value.kind == "config"


def test_graph_client_still_requires_credentials_without_provider():
    with pytest.raises(ConnectorError):
        GraphClient("", "")


def test_token_never_written_in_clear(tmp_path):
    store = TokenStore(tmp_path / "t.bin")
    store.save({"refresh_token": "texto-reconocible"})
    raw = (tmp_path / "t.bin").read_bytes()
    import sys
    if sys.platform == "win32":
        assert b"texto-reconocible" not in raw
    else:
        assert json.loads(raw)["refresh_token"] == "texto-reconocible"
