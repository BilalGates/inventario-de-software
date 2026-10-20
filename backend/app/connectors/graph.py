"""Cliente mínimo de Microsoft Graph con autenticación de aplicación, paginación y reintentos.

- Client credentials con secreto o, preferiblemente, con certificado (client assertion).
- Paginación por @odata.nextLink.
- 429/503/504 y errores de red: reintento con backoff exponencial respetando Retry-After.
- 401: renueva el token una vez. 403: error de permisos, sin reintento.
- Nunca registra tokens ni secretos.
"""
from __future__ import annotations

import base64
import hashlib
import random
import time
import uuid
from collections.abc import Callable, Iterator
from typing import Any

import httpx
import jwt

from app.connectors.base import ConnectorError

RETRYABLE = {429, 500, 502, 503, 504}


class GraphClient:
    def __init__(
        self,
        tenant_id: str,
        client_id: str,
        client_secret: str = "",
        certificate_path: str = "",
        certificate_thumbprint: str = "",
        base_url: str = "https://graph.microsoft.com",
        max_retries: int = 5,
        http: httpx.Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
        token_provider: Callable[[bool], str] | None = None,
    ):
        # token_provider: acceso delegado (sesión de usuario); sustituye a las credenciales de aplicación.
        self._token_provider = token_provider
        if not token_provider and (not tenant_id or not client_id or not (client_secret or certificate_path)):
            raise ConnectorError("Credenciales de Microsoft Graph no configuradas.", kind="config")
        self.tenant_id = tenant_id
        self.client_id = client_id
        self._secret = client_secret
        self._cert_path = certificate_path
        self._thumbprint = certificate_thumbprint
        self.base_url = base_url.rstrip("/")
        self.max_retries = max_retries
        self.http = http or httpx.Client(timeout=httpx.Timeout(60.0, connect=15.0))  # verify=True por defecto
        self.sleep = sleep
        self._token: str | None = None
        self._token_exp = 0.0
        self.request_count = 0
        self.throttled_count = 0

    # -- autenticación -----------------------------------------------------------------
    def _client_assertion(self) -> str:
        with open(self._cert_path, "rb") as fh:
            pem = fh.read()
        thumb = bytes.fromhex(self._thumbprint.replace(":", ""))
        now = int(time.time())
        claims = {
            "aud": f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token",
            "iss": self.client_id,
            "sub": self.client_id,
            "jti": str(uuid.uuid4()),
            "nbf": now,
            "exp": now + 600,
        }
        headers = {"x5t": base64.urlsafe_b64encode(thumb).decode().rstrip("=")}
        return jwt.encode(claims, pem, algorithm="RS256", headers=headers)

    def _get_token(self) -> str:
        if self._token_provider:
            force = self._token is None  # tras un 401 se fuerza la renovación
            self._token = self._token_provider(force)
            return self._token
        if self._token and time.time() < self._token_exp - 120:
            return self._token
        data = {
            "client_id": self.client_id,
            "scope": "https://graph.microsoft.com/.default",
            "grant_type": "client_credentials",
        }
        if self._cert_path:
            data["client_assertion_type"] = "urn:ietf:params:oauth:client-assertion-type:jwt-bearer"
            data["client_assertion"] = self._client_assertion()
        else:
            data["client_secret"] = self._secret
        url = f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token"
        try:
            resp = self.http.post(url, data=data)
        except httpx.HTTPError as exc:
            raise ConnectorError(f"No se pudo contactar con Entra ID: {type(exc).__name__}", kind="network") from exc
        if resp.status_code != 200:
            code = _safe_error_code(resp)
            raise ConnectorError(f"Autenticación con Entra ID rechazada ({resp.status_code} {code}).", kind="auth")
        body = resp.json()
        self._token = body["access_token"]
        self._token_exp = time.time() + int(body.get("expires_in", 3600))
        return self._token

    # -- peticiones --------------------------------------------------------------------
    def get(self, path_or_url: str, params: dict[str, Any] | None = None) -> dict:
        url = path_or_url if path_or_url.startswith("http") else f"{self.base_url}{path_or_url}"
        refreshed = False
        attempt = 0
        while True:
            attempt += 1
            headers = {"Authorization": f"Bearer {self._get_token()}", "ConsistencyLevel": "eventual"}
            try:
                self.request_count += 1
                resp = self.http.get(url, params=params, headers=headers)
            except httpx.HTTPError as exc:
                if attempt > self.max_retries:
                    raise ConnectorError(f"Error de red con Graph tras {attempt} intentos: {type(exc).__name__}",
                                         kind="network") from exc
                self.sleep(self._backoff(attempt, None))
                continue
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code == 401 and not refreshed:
                refreshed = True
                self._token = None
                continue
            if resp.status_code == 403:
                raise ConnectorError(
                    f"Permisos insuficientes en Graph para {_path(url)} ({_safe_error_code(resp)}).", kind="permission"
                )
            if resp.status_code in RETRYABLE and attempt <= self.max_retries:
                if resp.status_code == 429:
                    self.throttled_count += 1
                self.sleep(self._backoff(attempt, resp.headers.get("Retry-After")))
                continue
            kind = "throttled" if resp.status_code == 429 else "error"
            raise ConnectorError(f"Graph respondió {resp.status_code} en {_path(url)} ({_safe_error_code(resp)}).",
                                 kind=kind)

    def paginate(self, path: str, params: dict[str, Any] | None = None) -> Iterator[dict]:
        page = self.get(path, params)
        while True:
            yield from page.get("value", [])
            next_link = page.get("@odata.nextLink")
            if not next_link:
                return
            page = self.get(next_link)  # el nextLink ya incluye los parámetros

    @staticmethod
    def _backoff(attempt: int, retry_after: str | None) -> float:
        if retry_after:
            try:
                return min(float(retry_after), 300.0)
            except ValueError:
                pass
        return min(2 ** attempt + random.uniform(0, 1), 120.0)


def _path(url: str) -> str:
    return httpx.URL(url).path


def _safe_error_code(resp: httpx.Response) -> str:
    """Solo el código de error, nunca el cuerpo completo (podría contener datos)."""
    try:
        body = resp.json()
        err = body.get("error")
        if isinstance(err, dict):
            return str(err.get("code", ""))[:80]
        return str(err or "")[:80]
    except Exception:
        return hashlib.sha256(resp.content[:200]).hexdigest()[:8]
