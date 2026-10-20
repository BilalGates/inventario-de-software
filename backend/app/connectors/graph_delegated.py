"""Inicio de sesión delegado en Microsoft Graph (código de dispositivo) para el conector de Intune.

Alternativa al registro de aplicación con secreto: el usuario inicia sesión una vez desde la web
con su propia cuenta y el servicio guarda el refresh token para renovar el acceso solo.

- Cliente público "Microsoft Graph Command Line Tools" (el mismo que usa el script PowerShell).
- El refresh token se guarda cifrado con DPAPI (solo lo descifra el usuario de Windows que lo
  guardó, en este equipo). Fuera de Windows (pruebas) se guarda con permisos 600.
- Nunca se registran tokens.
"""
from __future__ import annotations

import json
import os
import sys
import threading
import time
from pathlib import Path
from typing import Any

import httpx
import jwt

from app.connectors.base import ConnectorError

CLIENT_ID = "14d82eec-204b-4c2f-b7e8-296a70dab67e"  # Microsoft Graph Command Line Tools (app pública de Microsoft)
SCOPE = "https://graph.microsoft.com/DeviceManagementManagedDevices.Read.All offline_access openid profile"
LOGIN = "https://login.microsoftonline.com"


# --------------------------------------------------------------------------- almacén cifrado
def _dpapi(data: bytes, protect: bool) -> bytes:
    import ctypes
    from ctypes import wintypes

    class Blob(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    buf = ctypes.create_string_buffer(data, len(data))
    src, out = Blob(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char))), Blob()
    crypt32 = ctypes.windll.crypt32
    fn = crypt32.CryptProtectData if protect else crypt32.CryptUnprotectData
    if not fn(ctypes.byref(src), None, None, None, None, 0x1, ctypes.byref(out)):  # 0x1: sin interfaz
        raise OSError("DPAPI no pudo procesar el token guardado.")
    try:
        return ctypes.string_at(out.pbData, out.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(out.pbData)


class TokenStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def exists(self) -> bool:
        return self.path.is_file()

    def load(self) -> dict[str, Any] | None:
        try:
            raw = self.path.read_bytes()
        except OSError:
            return None
        try:
            if sys.platform == "win32":
                raw = _dpapi(raw, protect=False)
            return json.loads(raw)
        except (OSError, ValueError):
            return None

    def save(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        raw = json.dumps(data).encode()
        if sys.platform == "win32":
            raw = _dpapi(raw, protect=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_bytes(raw)
        if sys.platform != "win32":
            os.chmod(tmp, 0o600)
        os.replace(tmp, self.path)

    def delete(self) -> None:
        self.path.unlink(missing_ok=True)


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


# --------------------------------------------------------------------------- inicio de sesión
class DeviceCodeLogin:
    """Flujo de código de dispositivo. Guarda en memoria el inicio de sesión pendiente (uno a la vez)."""

    def __init__(self, store: TokenStore, http: httpx.Client | None = None):
        self.store = store
        self.http = http or httpx.Client(timeout=httpx.Timeout(30.0, connect=15.0))
        self._pending: dict[str, Any] | None = None
        self._lock = threading.Lock()

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

    def __init__(self, store: TokenStore, http: httpx.Client | None = None):
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
