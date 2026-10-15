"""Autenticación (Microsoft Entra ID) y autorización por roles, aplicada en el backend.

Roles (jerárquicos): admin > technician > auditor.
- En modo "entra" el rol sale de los *app roles* del token (claim `roles`), asignados en
  Entra ID a usuarios o grupos. La aplicación no almacena contraseñas.
- En modo "dev" (prohibido en producción) se usa una identidad fija de configuración.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import jwt
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db import get_db, utcnow
from app.models import User

ROLE_RANK = {"auditor": 1, "technician": 2, "admin": 3}


@dataclass(frozen=True)
class CurrentUser:
    upn: str
    name: str | None
    role: str
    oid: str | None = None

    def can(self, role: str) -> bool:
        return ROLE_RANK.get(self.role, 0) >= ROLE_RANK[role]


@lru_cache(maxsize=4)
def _jwks_client(tenant_id: str) -> jwt.PyJWKClient:
    return jwt.PyJWKClient(f"https://login.microsoftonline.com/{tenant_id}/discovery/v2.0/keys", cache_keys=True)


def _role_from_claims(claims: dict, s: Settings) -> str | None:
    roles = set(claims.get("roles") or [])
    for internal, external in (("admin", s.entra_role_admin), ("technician", s.entra_role_technician),
                               ("auditor", s.entra_role_auditor)):
        if external in roles:
            return internal
    return None


def decode_entra_token(token: str, s: Settings, key_resolver=None) -> dict:
    key = (key_resolver or (lambda t: _jwks_client(s.entra_tenant_id).get_signing_key_from_jwt(t).key))(token)
    return jwt.decode(
        token,
        key,
        algorithms=["RS256"],
        audience=[s.entra_api_client_id, f"api://{s.entra_api_client_id}"],
        issuer=f"https://login.microsoftonline.com/{s.entra_tenant_id}/v2.0",
        options={"require": ["exp", "iat", "aud", "iss"]},
    )


def get_current_user(request: Request, db: Session = Depends(get_db),
                     settings: Settings = Depends(get_settings)) -> CurrentUser:
    if settings.auth_mode == "dev":
        return CurrentUser(upn=settings.dev_user_upn, name="Desarrollo", role=settings.dev_user_role)
    if settings.auth_mode == "local":
        # Servicio en el propio equipo: la configuración garantiza que solo escucha en 127.0.0.1.
        # Se rechaza además cualquier petición que no venga del propio equipo.
        if request.client and request.client.host not in ("127.0.0.1", "::1", "testclient"):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Acceso solo desde este equipo")
        return CurrentUser(upn=settings.local_user_upn, name="Administrador local", role="admin")

    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Autenticación requerida",
                            headers={"WWW-Authenticate": "Bearer"})
    try:
        claims = decode_entra_token(header[7:], settings, getattr(request.app.state, "jwt_key_resolver", None))
    except jwt.PyJWTError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token no válido",
                            headers={"WWW-Authenticate": "Bearer"}) from exc
    if claims.get("tid") and claims["tid"] != settings.entra_tenant_id:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Tenant no autorizado")
    role = _role_from_claims(claims, settings)
    if role is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Su cuenta no tiene un rol asignado en Inventario Asserta")
    upn = (claims.get("preferred_username") or claims.get("upn") or claims.get("oid") or "").lower()
    user = CurrentUser(upn=upn, name=claims.get("name"), role=role, oid=claims.get("oid"))
    _touch_user(db, user)
    return user


def _touch_user(db: Session, user: CurrentUser) -> None:
    row = db.execute(select(User).where(User.upn == user.upn)).scalar_one_or_none()
    if row is None:
        row = User(upn=user.upn, display_name=user.name, source="entra")
        db.add(row)
    row.role, row.entra_object_id, row.last_login_at = user.role, user.oid or row.entra_object_id, utcnow()
    if user.name:
        row.display_name = user.name
    db.commit()


def require(role: str):
    def dep(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if not user.can(role):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Permisos insuficientes para esta operación")
        return user

    return dep


Reader = Depends(require("auditor"))
Technician = Depends(require("technician"))
Admin = Depends(require("admin"))
