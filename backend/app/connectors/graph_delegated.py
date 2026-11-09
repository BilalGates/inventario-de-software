"""Inicio de sesión delegado en Microsoft Graph (código de dispositivo) para el conector de Intune.

Alternativa al registro de aplicación con secreto: el usuario inicia sesión una vez desde la web
con su propia cuenta y el servicio guarda el refresh token para renovar el acceso solo.

- Cliente público "Microsoft Graph Command Line Tools" (el mismo que usa el script PowerShell).
- El refresh token se guarda en la base de datos cifrado con AES-GCM y la clave
  INV_TOKEN_ENCRYPTION_KEY, que solo conocen Vercel y GitHub Actions. El inicio de sesión pendiente
  también va a la base: en Vercel cada petición puede atenderla una instancia distinta.
- Nunca se registran tokens.
"""
from __future__ import annotations

import base64
import json
import os
import threading
import time
from typing import Any

import httpx
import jwt

from app.connectors.base import ConnectorError

CLIENT_ID = "14d82eec-204b-4c2f-b7e8-296a70dab67e"  # Microsoft Graph Command Line Tools (app pública de Microsoft)
SCOPE = "https://graph.microsoft.com/DeviceManagementManagedDevices.Read.All offline_access openid profile"
LOGIN = "https://login.microsoftonline.com"


def _account(id_token: str | None) -> dict[str, str]:
    """Solo para mostrar quién está conectado; la validez la garantiza Entra al emitir los tokens."""
    if not id_token:
        return {}
    try:
        claims = jwt.decode(id_token, options={"verify_signature": False})
    except jwt.PyJWTError:
        return {}
    return {"account": claims.get("preferred_username") or claims.get("upn") or claims.get("name") or "",
            "tenant_id": claims.get("tid") or ""}


def _error_code(resp: httpx.Response) -> str:
    try:
        return str(resp.json().get("error", ""))[:80]
    except ValueError:
        return str(resp.status_code)


def decode_key(secret: str) -> bytes:
    """Clave AES-256 en base64 (32 bytes). Genérela con: python -c "import os,base64;print(base64.b64encode(os.urandom(32)).decode())"."""
    try:
        key = base64.b64decode(secret.strip(), validate=True)
    except ValueError:
        key = b""
    if len(key) != 32:
        raise ValueError("INV_TOKEN_ENCRYPTION_KEY debe ser una clave de 32 bytes en base64.")
    return key


class EncryptedSettingStore:
    """Almacén de un dict en la tabla app_settings, cifrado con AES-GCM (load/save/delete/exists)."""

    def __init__(self, setting_key: str, secret: str):
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM

        self.setting_key = setting_key
        self._aes = AESGCM(decode_key(secret))

    def _row(self, db):
        from app.models import AppSetting

        return db.get(AppSetting, self.setting_key)

    def exists(self) -> bool:
        return self.load() is not None

    def load(self) -> dict[str, Any] | None:
        from cryptography.exceptions import InvalidTag

        from app.db import session_scope

        with session_scope() as db:
            row = self._row(db)
            raw = row.value if row else None
        if not isinstance(raw, dict):
            return None
        try:
            data = self._aes.decrypt(base64.b64decode(raw["nonce"]), base64.b64decode(raw["data"]),
                                     self.setting_key.encode())
            return json.loads(data)
        except (KeyError, ValueError, InvalidTag):
            return None  # clave distinta o dato manipulado: como si no hubiera sesión

    def save(self, data: dict[str, Any]) -> None:
        from app.db import session_scope
        from app.models import AppSetting

        nonce = os.urandom(12)
        sealed = self._aes.encrypt(nonce, json.dumps(data).encode(), self.setting_key.encode())
        with session_scope() as db:
            row = self._row(db) or AppSetting(key=self.setting_key)
            row.value = {"v": 1, "nonce": base64.b64encode(nonce).decode(), "data": base64.b64encode(sealed).decode()}
            row.updated_by = "system:graph"
            db.add(row)

    def delete(self) -> None:
        from app.db import session_scope

        with session_scope() as db:
            row = self._row(db)
            if row is not None:
                db.delete(row)


# --------------------------------------------------------------------------- inicio de sesión
class DeviceCodeLogin:
    """Flujo de código de dispositivo (uno a la vez). El inicio de sesión pendiente se guarda en
    memoria o, si se da pending_store, en ese almacén (necesario cuando cada petición la atiende
    una instancia distinta, como en Vercel)."""

    def __init__(self, store: EncryptedSettingStore, http: httpx.Client | None = None, pending_store: Any = None):
        self.store = store
        self.pending_store = pending_store
        self.http = http or httpx.Client(timeout=httpx.Timeout(30.0, connect=15.0))
        self._memory: dict[str, Any] | None = None
        self._lock = threading.Lock()

    @property
    def _pending(self) -> dict[str, Any] | None:
        return self.pending_store.load() if self.pending_store is not None else self._memory

    @_pending.setter
    def _pending(self, value: dict[str, Any] | None) -> None:
        if self.pending_store is None:
            self._memory = value
        elif value is None:
            self.pending_store.delete()
        else:
            self.pending_store.save(value)

    def start(self) -> dict[str, Any]:
        resp = self._post(f"{LOGIN}/organizations/oauth2/v2.0/devicecode", {"client_id": CLIENT_ID, "scope": SCOPE})
        if resp.status_code != 200:
            raise ConnectorError(f"Entra ID rechazó el inicio de sesión ({_error_code(resp)}).", kind="auth")
        body = resp.json()
        with self._lock:
            self._pending = {"device_code": body["device_code"], "expires_at": time.time() + int(body["expires_in"]),
                             "interval": int(body.get("interval", 5)), "next_poll": 0.0}
        return {"user_code": body["user_code"], "verification_uri": body["verification_uri"],
                "expires_in": int(body["expires_in"]), "interval": int(body.get("interval", 5))}

    def poll(self) -> dict[str, Any]:
        """Una comprobación (la web la repite). Estados: pending, connected, expired, error, idle."""
        with self._lock:
            pending = self._pending
            if pending is None:
                return {"status": "idle"}
            if time.time() > pending["expires_at"]:
                self._pending = None
                return {"status": "expired"}
            if time.time() < pending["next_poll"]:
                return {"status": "pending"}
            pending["next_poll"] = time.time() + pending["interval"]
            self._pending = pending
        resp = self._post(f"{LOGIN}/organizations/oauth2/v2.0/token", {
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code", "client_id": CLIENT_ID,
            "device_code": pending["device_code"]})
        if resp.status_code == 200:
            body = resp.json()
            info = _account(body.get("id_token"))
            self.store.save({"refresh_token": body["refresh_token"], **info, "connected_at": int(time.time())})
            with self._lock:
                self._pending = None
            return {"status": "connected", "account": info.get("account", "")}
        code = _error_code(resp)
        if code == "authorization_pending":
            return {"status": "pending"}
        if code == "slow_down":
            with self._lock:
                pending["interval"] += 5
                self._pending = pending
            return {"status": "pending"}
        with self._lock:
            self._pending = None
        if code == "expired_token":
            return {"status": "expired"}
        return {"status": "error", "error": f"Inicio de sesión rechazado ({code})."}

    def _post(self, url: str, data: dict[str, str]) -> httpx.Response:
        try:
            return self.http.post(url, data=data)
        except httpx.HTTPError as exc:
            raise ConnectorError(f"No se pudo contactar con Entra ID: {type(exc).__name__}", kind="network") from exc


# --------------------------------------------------------------------------- tokens para el conector
class DelegatedTokenProvider:
    """Entrega access tokens a GraphClient renovándolos con el refresh token guardado."""

    def __init__(self, store: EncryptedSettingStore, http: httpx.Client | None = None):
        self.store = store
        self.http = http or httpx.Client(timeout=httpx.Timeout(30.0, connect=15.0))
        self._token: str | None = None
        self._exp = 0.0

    def __call__(self, force: bool = False) -> str:
        if self._token and not force and time.time() < self._exp - 120:
            return self._token
        saved = self.store.load()
        if not saved or not saved.get("refresh_token"):
            raise ConnectorError("No hay sesión de Microsoft iniciada para Intune. Conéctese desde Sincronización.",
                                 kind="config")
        tenant = saved.get("tenant_id") or "organizations"
        try:
            resp = self.http.post(f"{LOGIN}/{tenant}/oauth2/v2.0/token", data={
                "grant_type": "refresh_token", "client_id": CLIENT_ID, "refresh_token": saved["refresh_token"],
                "scope": SCOPE})
        except httpx.HTTPError as exc:
            raise ConnectorError(f"No se pudo contactar con Entra ID: {type(exc).__name__}", kind="network") from exc
        if resp.status_code != 200:
            code = _error_code(resp)
            if code in ("invalid_grant", "interaction_required"):
                raise ConnectorError("La sesión de Microsoft ha caducado. Vuelva a conectar desde Sincronización.",
                                     kind="auth")
            raise ConnectorError(f"Entra ID rechazó la renovación del token ({code}).", kind="auth")
        body = resp.json()
        if body.get("refresh_token"):  # Entra rota el refresh token: hay que guardar el nuevo
            self.store.save({**saved, "refresh_token": body["refresh_token"]})
        self._token = body["access_token"]
        self._exp = time.time() + int(body.get("expires_in", 3600))
        return self._token
