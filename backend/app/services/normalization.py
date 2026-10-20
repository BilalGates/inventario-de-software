"""Normalización conservadora de software y dispositivos.

Principio: solo se unifican variantes que son el mismo texto salvo ruido tipográfico
(mayúsculas, espacios, símbolos ®/™, la versión repetida al final del nombre). Productos
con nombres parecidos NO se fusionan; para eso existen los alias manuales.
"""
from __future__ import annotations

import re
import unicodedata

from app.legacy import clean_version

_TM = re.compile(r"[®™©]")
_WS = re.compile(r"\s+")
_PUBLISHER_SUFFIX = re.compile(
    r"[,.]?\s+(inc|incorporated|corp|corporation|co|company|llc|ltd|limited|gmbh|s\.?a\.?|s\.?l\.?|ag|b\.?v\.?)\.?$",
    re.IGNORECASE,
)

# Números de serie de relleno que ponen algunos fabricantes: nunca sirven para conciliar.
_JUNK_SERIALS = {
    "", "0", "00000000", "0123456789", "none", "n/a", "na", "unknown", "default string",
    "to be filled by o.e.m.", "system serial number", "chassis serial number", "not applicable",
    "invalid", "123456789",
}


def _base(value: str | None) -> str:
    val = unicodedata.normalize("NFKC", str(value or ""))
    val = _TM.sub("", val)
    return _WS.sub(" ", val).strip()


def name_key(name: str | None, version: str | None = None) -> str:
    """Clave de identidad del nombre. Quita la versión solo si aparece literalmente al final."""
    val = _base(name)
    ver = clean_version(version)
    if ver:
        for sep in (" - ", " ", " v", " - v"):
            suffix = f"{sep}{ver}"
            if val.casefold().endswith(suffix.casefold()) and len(val) > len(suffix):
                val = val[: -len(suffix)].rstrip(" -")
                break
    return val.casefold()[:190]


# Valor entre comillas (Intune a veces las duplica: CN="Pulse Secure, LLC"") o hasta la coma.
_DN_ATTR = re.compile(r'(?:^|,)\s*(CN|O)=(?:"+([^"]*)"*|([^,]*))', re.IGNORECASE)
_GUID = re.compile(r"^[0-9A-F]{8}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{12}$", re.IGNORECASE)
# Paquete MSIX/AppX de Microsoft o Windows: "Microsoft.BingNews", "MicrosoftWindows.Client.WebExperience",
# "WindowsWorkload.Manager…". Los de otros fabricantes (4DF9E0F8.Netflix, DellInc.MyDell…) son aplicaciones.
_WINDOWS_PACKAGE = re.compile(r"^(microsoft|microsoftwindows|microsoftcorporationii|windows|windowsworkload)"
                              r"(\.[A-Za-z0-9_-]+)+$", re.IGNORECASE)


def is_certificate_subject(publisher: str | None) -> bool:
    """Las apps MSIX/AppX informan el editor como sujeto del certificado: "CN=..., O=..., C=US"."""
    return bool(re.search(r"(^|,)\s*CN=", str(publisher or ""), re.IGNORECASE))


def clean_publisher(publisher: str | None) -> str | None:
    """Editor legible. Del sujeto de certificado toma CN (o O si CN es un GUID de la Store)."""
    val = _base(publisher)
    if not is_certificate_subject(val):
        return val or None
    attrs: dict[str, str] = {}
    for key, quoted, plain in _DN_ATTR.findall(val):
        attrs.setdefault(key.upper(), (quoted or plain).strip())
    for key in ("CN", "O"):
        if attrs.get(key) and not _GUID.match(attrs[key]):
            return attrs[key][:200]
    return None  # solo GUID: la Store no publica el nombre del editor


def publisher_key(publisher: str | None) -> str:
    val = _base(clean_publisher(publisher)).casefold().rstrip(".")
    prev = None
    while prev != val:  # "Foo Corp., Inc." -> "foo"
        prev = val
        val = _PUBLISHER_SUFFIX.sub("", val).strip().rstrip(",.")
    return val[:120]


def display_name(name: str | None, version: str | None = None) -> str:
    val = _base(name)
    key = name_key(val, version)
    return val[: len(key)] if key and val.casefold().startswith(key) else val


def version_text(version: str | None) -> str:
    return (clean_version(version) or "")[:150]


_RULES: list[tuple[str, re.Pattern]] = [
    ("update", re.compile(r"\b(kb\d{6,}|security update|update for|hotfix|cumulative update)\b", re.I)),
    ("driver", re.compile(r"\b(driver|controlador|chipset|firmware)\b", re.I)),
    (
        "runtime",
        re.compile(
            r"(visual c\+\+ .*redistributable|\.net (framework|runtime|desktop runtime)|"
            r"\bjava\(?tm\)?\b.*\b(update|runtime)\b|windows desktop runtime|webview2 runtime|vcredist)",
            re.I,
        ),
    ),
    (
        "system_component",
        re.compile(
            r"^(microsoft (update health tools|windows sdk|gameinput|policy platform)|"
            r"windows (sdk|software development kit|pc health check)|intel\(r\) .*(management|serial io|"
            r"rapid storage)|realtek .*(audio|card reader))",
            re.I,
        ),
    ),
]


def classify(name: str | None, publisher: str | None = None) -> str:
    """Clasificación orientativa. IT puede cambiarla y la manual nunca se sobrescribe."""
    text = _base(name)
    # Solo por el nombre: el editor llega limpio (sin "CN=") tras normalizarlo, y los programas de
    # escritorio de Microsoft se llaman con espacios ("Microsoft Edge", "Microsoft .NET Runtime").
    if _WINDOWS_PACKAGE.match(text):
        # Paquetes de Windows (Microsoft.BingNews, Microsoft.NET.Native.Runtime…, códecs, idiomas), no programas.
        return "system_component"
    for category, pattern in _RULES:
        if pattern.search(text):
            return category
    return "application" if text else "unknown"


def serial_key(serial: str | None) -> str | None:
    val = _base(serial).upper()
    if val.casefold() in _JUNK_SERIALS or len(val) < 4 or len(set(val)) == 1:
        return None
    return val


def hostname_key(hostname: str | None) -> str | None:
    val = _base(hostname).upper()
    if not val:
        return None
    return val.split(".")[0]  # quita sufijo DNS
