"""Conformidad de Intune: por qué un equipo no es conforme y acciones remotas para corregirlo.

Lectura (DeviceManagementConfiguration.Read.All):
  GET {api}/deviceManagement/managedDevices/{id}/deviceCompliancePolicyStates
  Cada directiva trae su estado y `settingStates` (ajuste, estado, error). Si v1.0 los devuelve vacíos
  se repite la consulta en beta, que suele detallarlos.
Acciones (DeviceManagementManagedDevices.PrivilegedOperations.All):
  POST managedDevices/{id}/syncDevice | windowsDefenderUpdateSignatures | windowsDefenderScan

La conformidad la evalúa el propio equipo: desde aquí solo se puede forzar que se reevalúe (sync) o
resolver causas concretas (firmas de Defender). El resto se explica con una pista de corrección.
"""
from __future__ import annotations

from typing import Any

from app.connectors.base import ConnectorError
from app.connectors.graph import GraphClient

# Estados de directiva/ajuste que explican un «No conforme».
FAILING = {"noncompliant", "error", "conflict"}
# Estados del equipo (complianceState) para los que merece la pena pedir el detalle.
DEVICE_FAILING = {"noncompliant", "error", "conflict", "ingraceperiod"}

# Acciones permitidas: código -> (acción de Graph, cuerpo, etiqueta).
ACTIONS: dict[str, tuple[str, dict | None, str]] = {
    "sync": ("syncDevice", None, "Sincronizar equipo"),
    "defender_signatures": ("windowsDefenderUpdateSignatures", None, "Actualizar firmas de Defender"),
    "defender_scan": ("windowsDefenderScan", {"quickScan": True}, "Análisis rápido de Defender"),
}

_PANDA = " Si el equipo usa Panda, comprobar que Panda está registrado en Seguridad de Windows o excluir este requisito."
# Último segmento del ajuste (p. ej. "Windows10CompliancePolicy.BitLockerEnabled") -> (texto, pista, acción).
SETTING_HINTS: dict[str, tuple[str, str, str | None]] = {
    "bitlockerenabled": ("BitLocker desactivado",
                         "Activar BitLocker en el equipo (o con un perfil de cifrado de Intune) y sincronizar.", "sync"),
    "storagerequireencryption": ("Almacenamiento sin cifrar",
                                 "Activar BitLocker en el equipo (o con un perfil de cifrado de Intune) y sincronizar.",
                                 "sync"),
    "securebootenabled": ("Arranque seguro desactivado", "Activar Secure Boot en la BIOS/UEFI y reiniciar.", None),
    "codeintegrityenabled": ("Integridad de código desactivada",
                             "Reiniciar el equipo; si persiste, revisar controladores no firmados.", "sync"),
    "tpmrequired": ("TPM no disponible", "Activar el TPM en la BIOS/UEFI.", None),
    "osminimumversion": ("Versión de Windows inferior a la mínima",
                         "Instalar las actualizaciones pendientes de Windows Update y sincronizar.", "sync"),
    "osmaximumversion": ("Versión de Windows superior a la permitida",
                         "Revisar la versión máxima permitida en la directiva.", None),
    "mobileosminimumversion": ("Versión del sistema inferior a la mínima", "Actualizar el sistema operativo.", "sync"),
    "defenderenabled": ("Microsoft Defender desactivado", "Activar Microsoft Defender Antivirus." + _PANDA, None),
    "rtpenabled": ("Protección en tiempo real desactivada",
                   "Activar la protección en tiempo real de Defender." + _PANDA, None),
    "signatureoutofdate": ("Firmas de Defender desactualizadas", "Actualizar las firmas de Defender.",
                           "defender_signatures"),
    "defenderversion": ("Versión de Defender antigua", "Actualizar Defender (plataforma y firmas).",
                        "defender_signatures"),
    "antivirusrequired": ("Sin antivirus activo en Seguridad de Windows",
                          "Activar un antivirus registrado en Seguridad de Windows." + _PANDA, None),
    "antispywarerequired": ("Sin antispyware activo en Seguridad de Windows",
                            "Activar un antispyware registrado en Seguridad de Windows." + _PANDA, None),
    "activefirewallrequired": ("Firewall desactivado", "Activar el Firewall de Windows.", None),
    "passwordrequired": ("Contraseña no exigida", "Configurar contraseña/PIN de inicio de sesión.", None),
    "devicethreatprotectionenabled": ("Riesgo de amenaza por encima del permitido",
                                      "Revisar las alertas del equipo en Microsoft Defender y analizarlo.",
                                      "defender_scan"),
    "devicethreatprotectionrequiredsecuritylevel": ("Riesgo de amenaza por encima del permitido",
                                                    "Revisar las alertas del equipo en Microsoft Defender y analizarlo.",
                                                    "defender_scan"),
    "requireremaincontact": ("Sin contacto reciente con Intune",
                             "Encender el equipo con conexión a Internet y sincronizarlo.", "sync"),
    "requireuserexistence": ("El usuario inscrito ya no existe", "Reasignar o reinscribir el equipo en Intune.", None),
    "requiredevicecompliancepolicyassigned": ("Sin directiva de conformidad asignada",
                                              "Asignar una directiva de conformidad al equipo o a su usuario.", None),
}


def _norm(value: Any) -> str:
    return str(value or "").strip().lower()


def explain(setting: str | None, setting_name: str | None) -> tuple[str, str | None, str | None]:
    """Texto legible, pista y acción sugerida de un ajuste. Lo desconocido se muestra tal cual."""
    key = _norm(setting).rsplit(".", 1)[-1]
    if key in SETTING_HINTS:
        return SETTING_HINTS[key]
    return (setting_name or setting or "Ajuste desconocido"), None, None


def _settings(raw: list[dict]) -> list[dict]:
    out = []
    for s in raw:
        if _norm(s.get("state")) not in FAILING:
            continue
        label, hint, action = explain(s.get("setting"), s.get("settingName"))
        out.append({"setting": s.get("setting"), "label": label, "hint": hint, "action": action,
                    "state": s.get("state"), "error": s.get("errorDescription") or None})
    return out


def fetch_compliance(client: GraphClient, intune_id: str, api_version: str = "v1.0") -> dict:
    """Directivas que fallan en el equipo, con sus ajustes. Vacío = ninguna directiva en fallo."""
    path = f"/deviceManagement/managedDevices/{intune_id}/deviceCompliancePolicyStates"
    states = list(client.paginate(f"/{api_version}{path}"))
    failing = [p for p in states if _norm(p.get("state")) in FAILING]
    if api_version != "beta" and any(not p.get("settingStates") for p in failing):
        try:  # v1.0 a veces no detalla los ajustes: beta sí
            beta = {p.get("id"): p for p in client.paginate(f"/beta{path}")}
        except ConnectorError as exc:
            if exc.kind in ("auth", "permission"):
                raise
            beta = {}
        failing = [p if p.get("settingStates") else beta.get(p.get("id"), p) for p in failing]
    policies = [{"name": p.get("displayName") or "Directiva sin nombre", "state": p.get("state"),
                 "settings": _settings(p.get("settingStates") or [])} for p in failing]
    return {"policies": policies}


def reasons(details: dict | None, state: str | None, limit: int = 4) -> list[str]:
    """Motivos cortos para la tabla (texto de cada ajuste o, si no hay detalle, la directiva). Solo
    con un estado en fallo: un motivo guardado nunca se muestra junto a un estado que ya no falla."""
    if _norm(state) not in DEVICE_FAILING:
        return []
    out: list[str] = []
    for p in (details or {}).get("policies", []):
        labels = [s["label"] for s in p.get("settings", [])] or [p.get("name")]
        out.extend(label for label in labels if label and label not in out)
    return out[:limit]


def run_action(client: GraphClient, intune_id: str, action: str, api_version: str = "v1.0") -> str:
    if action not in ACTIONS:
        raise ValueError(f"Acción no permitida: {action}")
    graph_action, body, label = ACTIONS[action]
    client.post(f"/{api_version}/deviceManagement/managedDevices/{intune_id}/{graph_action}", json=body)
    return label
