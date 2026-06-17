"""
Tokens de diseño — fuente única de verdad del lenguaje visual.

Centraliza color, espaciado, radios, tipografía y alturas para que todo el QSS y
los componentes se construyan desde aquí (sin números mágicos repartidos).

Se integra con `ui/theme.py`, que construye el QSS a partir de estos tokens
(no se duplican valores en ficheros .qss estáticos).
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# Paletas (claro / oscuro)
# ---------------------------------------------------------------------------
# El color SOLO se usa para acción, estado y alerta. Los grises sostienen el
# resto de la interfaz (minimalismo corporativo).

PALETTES: dict[str, dict[str, str]] = {
    "light": {
        "bg_primary": "#f6f7f9",     # fondo app
        "bg_secondary": "#ffffff",   # superficie / tarjetas
        "bg_tertiary": "#eef1f5",    # superficie hundida / deshabilitado
        "bg_hover": "#eef2f7",       # hover sutil
        "bg_active": "#eaf1fe",      # selección/activo suave (derivado del accent)

        "text_primary": "#111827",
        "text_secondary": "#6b7280",
        "text_muted": "#9ca3af",
        "text_on_accent": "#ffffff",

        "accent": "#2563eb",
        "accent_hover": "#1d4ed8",
        "accent_soft": "#eaf1fe",    # fondo suave para chips/sección activa

        "success": "#15803d",
        "success_soft": "#dcfce7",
        "warning": "#b45309",
        "warning_soft": "#fef3c7",
        "danger": "#b91c1c",
        "danger_soft": "#fee2e2",
        "info": "#1d4ed8",
        "info_soft": "#e0ecff",
        "neutral": "#6b7280",
        "neutral_soft": "#f1f3f5",

        "border": "#e5e7eb",
        "border_strong": "#d1d5db",
        "border_focus": "#2563eb",
    },
    "dark": {
        "bg_primary": "#0f1623",
        "bg_secondary": "#161f2e",
        "bg_tertiary": "#1e293b",
        "bg_hover": "#1f2c40",
        "bg_active": "#1e3a5f",

        "text_primary": "#e5e7eb",
        "text_secondary": "#9aa6b6",
        "text_muted": "#6b7a8d",
        "text_on_accent": "#0b1220",

        "accent": "#3b82f6",
        "accent_hover": "#60a5fa",
        "accent_soft": "#17304f",

        "success": "#4ade80",
        "success_soft": "#10301f",
        "warning": "#fbbf24",
        "warning_soft": "#33270d",
        "danger": "#f87171",
        "danger_soft": "#3a1719",
        "info": "#60a5fa",
        "info_soft": "#11233b",
        "neutral": "#94a3b8",
        "neutral_soft": "#1b2535",

        "border": "#2a3647",
        "border_strong": "#3a485c",
        "border_focus": "#3b82f6",
    },
}

# ---------------------------------------------------------------------------
# Escalas (idénticas en claro/oscuro)
# ---------------------------------------------------------------------------

SPACING = {"xs": 4, "sm": 8, "md": 12, "lg": 16, "xl": 24, "xxl": 32}

RADIUS = {"sm": 6, "md": 8, "lg": 12, "pill": 999}

FONT = {
    "family": "'Segoe UI', 'Inter', 'Helvetica Neue', Arial, sans-serif",
    "title": 22,        # título de página
    "section": 15,      # cabecera de sección / tarjeta
    "subtitle": 13,     # descripción gris
    "body": 13,         # texto normal
    "small": 12,        # tabla / texto auxiliar
    "tiny": 11,         # etiquetas en mayúsculas / badges
    "metric": 26,       # valor de KPI
}

HEIGHT = {
    "button": 36,
    "input": 36,
    "row": 38,          # alto de fila de tabla
    "header_row": 40,   # alto de cabecera de tabla
}

# ---------------------------------------------------------------------------
# Estados semánticos → claves de color (texto / fondo suave)
# ---------------------------------------------------------------------------
# Cada estado mapea a un par (color de texto, color de fondo suave) del tema.
# No se depende solo del color: el badge SIEMPRE lleva texto.

STATUS_TONES = {
    "success": ("success", "success_soft"),
    "warning": ("warning", "warning_soft"),
    "danger": ("danger", "danger_soft"),
    "info": ("info", "info_soft"),
    "accent": ("accent", "accent_soft"),
    "neutral": ("neutral", "neutral_soft"),
}

# Etiquetas de dominio → tono semántico. Permite pintar estados de negocio
# (autorización, presencia, importación...) de forma consistente.
STATUS_LABELS = {
    # Autorización
    "autorizado": "success",
    "correcto": "success",
    "compliant": "success",
    "reactivado": "info",
    "exclusivo": "accent",
    "específico": "accent",
    "especifico": "accent",
    "general": "info",
    "multidispositivo": "info",
    "servidor": "info",
    "activo": "success",
    "inactivo": "neutral",
    "paste": "neutral",
    "archivo": "neutral",
    "file": "neutral",
    "pendiente": "warning",
    "incompleto": "warning",
    "no autorizado": "danger",
    "no presente": "neutral",
    "no compliant": "danger",
    "error": "danger",
    # Importación / cambios
    "nuevo": "success",
    "cambio version": "warning",
    "cambio de versión": "warning",
    "sin cambios": "neutral",
    "eliminado": "danger",
    "al día": "success",
    "al dia": "success",
    "atención": "warning",
    "atrasado": "danger",
    "nunca importado": "danger",
    # Guía 105
    "sí": "success",
    "si": "success",
    "no": "danger",
}


def tone_for_label(label: str) -> str:
    """Devuelve el tono semántico (success/warning/...) para una etiqueta de estado."""
    return STATUS_LABELS.get((label or "").strip().casefold(), "neutral")


def badge_colors(palette: dict[str, str], tone: str) -> tuple[str, str]:
    """(color_texto, color_fondo) para un tono semántico dado un tema."""
    text_key, bg_key = STATUS_TONES.get(tone, STATUS_TONES["neutral"])
    return palette[text_key], palette[bg_key]
