"""Dónde vive la sesión de Microsoft (código de dispositivo) que usa el conector de Intune.

- Nube (INV_TOKEN_ENCRYPTION_KEY definida): en la base de datos, cifrada con AES-GCM. La web
  (Vercel) inicia la sesión y el worker (GitHub Actions) la usa y guarda el token renovado.
- Windows: fichero cifrado con DPAPI en %LOCALAPPDATA%\\InventarioAsserta (como hasta ahora).
- Sin ninguna de las dos: no hay sesión posible; queda el registro de aplicación (INV_GRAPH_*).
"""
from __future__ import annotations

from typing import Any

from app.connectors.graph_delegated import EncryptedSettingStore, TokenStore
from app.core.config import get_settings

TOKEN_KEY = "secret.graph.session"
PENDING_KEY = "secret.graph.device_login"


def token_store() -> EncryptedSettingStore | TokenStore | None:
    s = get_settings()
    if s.token_encryption_key:
        return EncryptedSettingStore(TOKEN_KEY, s.token_encryption_key)
    if s.graph_token_path:
        return TokenStore(s.graph_token_path)
    return None


def pending_store() -> EncryptedSettingStore | None:
    """Inicio de sesión pendiente compartido entre instancias (solo en la nube)."""
    s = get_settings()
    return EncryptedSettingStore(PENDING_KEY, s.token_encryption_key) if s.token_encryption_key else None


def saved_session() -> dict[str, Any] | None:
    store = token_store()
    return store.load() if store is not None else None


def configured() -> bool:
    """Intune puede sincronizar: credenciales de aplicación o sesión de usuario guardada."""
    if get_settings().graph_app_configured:
        return True
    saved = saved_session()
    return bool(saved and saved.get("refresh_token"))
