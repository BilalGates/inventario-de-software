"""Excel de software por departamento.

- Una hoja por departamento (y "Sin departamento" si hay equipos sin asignar): cada programa
  instalado en sus equipos con el número de equipos y cuáles son. Las filas de programas que
  solo están en un equipo del departamento se marcan en amarillo.
- Última hoja: inventario de equipos agrupado por departamento (las mismas columnas que la
  exportación de dispositivos), con una fila de título por departamento.
"""
from __future__ import annotations

import io
import re
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from sqlalchemy import false, select
from sqlalchemy.orm import Session

from app.api.common import _cell, _csv_safe
from app.models import Department, Device, SoftwareInstallation, SoftwareProduct, SoftwareVersion

CATEGORY_LABEL = {"application": "Aplicación", "system_component": "Componente del sistema", "driver": "Controlador",
                  "runtime": "Runtime / librería", "update": "Actualización", "unknown": "Desconocido"}
AUTH_LABEL = {"authorized": "Autorizado", "unauthorized": "No autorizado", "pending_review": "Pendiente de revisión",
              "exception": "Excepción aprobada", "unclassified": "No clasificado"}
DEVICE_STATUS_LABEL = {"active": "En uso", "in_stock": "En almacén", "repair": "En reparación",
                       "retired": "Dado de baja", "lost": "Perdido / robado"}

HEADER_FILL = PatternFill("solid", fgColor="1F2937")
SINGLE_FILL = PatternFill("solid", fgColor="FFF2CC")  # amarillo claro: programa en un solo equipo
GROUP_FILL = PatternFill("solid", fgColor="E5E7EB")  # fila de título de cada departamento
SOFTWARE_COLUMNS = [("Programa", 45), ("Editor", 30), ("Categoría", 22), ("Autorización", 22), ("Versiones", 28),
                    ("Nº equipos", 11), ("Equipos", 70)]
NO_DEPARTMENT = "Sin departamento"


def _sheet_title(name: str, used: set[str]) -> str:
    base = re.sub(r"[\[\]:*?/\\]", "-", name).strip("'")[:31] or "Hoja"
    title, n = base, 2
    while title.lower() in used:
        suffix = f" ({n})"
        title, n = base[:31 - len(suffix)] + suffix, n + 1
    used.add(title.lower())
    return title


def _header(ws, row: int, titles: list[str]) -> None:
    for col, title in enumerate(titles, 1):
        cell = ws.cell(row, col, title)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(vertical="center")


@dataclass(frozen=True)
class Install:
    """Una instalación para el informe. `authorization`: None = estado actual del producto."""
    device_id: int
    department: str  # nombre del departamento (NO_DEPARTMENT si no tiene)
    device_label: str
    product_id: int
    version: str
    authorization: str | None = None


def live_installs(db: Session, product_ids: set[int], department_id: int | None) -> list[Install]:
    """Instalaciones vigentes (exportación de Software)."""
    departments = dict(db.execute(select(Department.id, Department.name)).all())
    query = (select(Device.id, Device.department_id, Device.hostname, Device.serial_number,
                    SoftwareInstallation.product_id, SoftwareVersion.version)
             .join(SoftwareInstallation, SoftwareInstallation.device_id == Device.id)
             .join(SoftwareVersion, SoftwareVersion.id == SoftwareInstallation.version_id)
             .where(SoftwareInstallation.present.is_(True), Device.status != "retired",
                    SoftwareInstallation.product_id.in_(product_ids) if product_ids else false()))
    if department_id:
        query = query.where(Device.department_id == department_id)
    return [Install(dev_id, departments.get(dept_id) or NO_DEPARTMENT, hostname or serial or f"#{dev_id}", pid,
                    version or "?") for dev_id, dept_id, hostname, serial, pid, version in db.execute(query)]


def build_workbook(db: Session, installs: list[Install], device_rows: list[dict],
                   device_columns: list[tuple[str, str]], generated: str,
                   only_department: str | None = None,
                   before: Callable[[Workbook, set[str]], None] | None = None,
                   after: Callable[[Workbook, set[str]], None] | None = None) -> bytes:
    """Hojas por departamento + inventario de equipos agrupado. `before`/`after` añaden hojas extra."""
    per_dept: dict[str, dict[int, dict[int, str]]] = defaultdict(lambda: defaultdict(dict))
    versions: dict[tuple[str, int], set[str]] = defaultdict(set)
    auths: dict[tuple[str, int], set[str]] = defaultdict(set)
    for i in installs:
        per_dept[i.department][i.product_id][i.device_id] = i.device_label
        versions[(i.department, i.product_id)].add(i.version)
        if i.authorization:
            auths[(i.department, i.product_id)].add(i.authorization)
    products = {p.id: p for p in db.execute(select(SoftwareProduct).where(
        SoftwareProduct.id.in_({i.product_id for i in installs}))).scalars()} if installs else {}
    dept_devices: dict[str, int] = defaultdict(int)
    for row in device_rows:
        dept_devices[row.get("department") or NO_DEPARTMENT] += 1

    wb = Workbook()
    wb.remove(wb.active)
    used: set[str] = set()
    if before:
        before(wb, used)
    order = sorted(set(per_dept) | ({only_department} if only_department else set()),
                   key=lambda n: (n == NO_DEPARTMENT, n.casefold()))
    for name in order:
        ws = wb.create_sheet(_sheet_title(name, used))
        prods = per_dept.get(name, {})
        single = sum(len(devs) == 1 for devs in prods.values())
        ws.cell(1, 1, name).font = Font(bold=True, size=14)
        ws.cell(2, 1, f"{dept_devices.get(name, 0)} equipos · {len(prods)} programas · "
                      f"{single} en un solo equipo (en amarillo) · {generated}").font = Font(italic=True,
                                                                                            color="6B7280")
        _header(ws, 4, [t for t, _ in SOFTWARE_COLUMNS])
        ordered = sorted(prods.items(), key=lambda kv: (-len(kv[1]), products[kv[0]].name.casefold()))
        for r, (pid, devs) in enumerate(ordered, 5):
            p = products[pid]
            status = auths.get((name, pid)) or {p.authorization_status}
            values = [p.name, p.publisher, CATEGORY_LABEL.get(p.category, p.category),
                      ", ".join(sorted(AUTH_LABEL.get(a, a) for a in status)),
                      ", ".join(sorted(versions[(name, pid)])), len(devs),
                      ", ".join(sorted(devs.values(), key=str.casefold))]
            for c, value in enumerate(values, 1):
                cell = ws.cell(r, c, _csv_safe(value))  # openpyxl trataría "=..." como fórmula
                if len(devs) == 1:
                    cell.fill = SINGLE_FILL
        for c, (_, width) in enumerate(SOFTWARE_COLUMNS, 1):
            ws.column_dimensions[get_column_letter(c)].width = width
        last = 4 + len(ordered)
        ws.auto_filter.ref = f"A4:{get_column_letter(len(SOFTWARE_COLUMNS))}{max(last, 5)}"
        ws.freeze_panes = "B5"

    # Inventario de equipos agrupado por departamento: una fila de título por grupo y sus equipos.
    ws = wb.create_sheet(_sheet_title("Inventario de equipos", used))
    _header(ws, 1, [t for _, t in device_columns])
    groups: dict[str, list[dict]] = defaultdict(list)
    for row in device_rows:
        groups[row.get("department") or NO_DEPARTMENT].append(row)
    r = 2
    for name in sorted(groups, key=lambda n: (n == NO_DEPARTMENT, n.casefold())):
        members = sorted(groups[name], key=lambda d: (d.get("name") or "").casefold())
        title = ws.cell(r, 1, f"{name} · {len(members)} equipos")
        title.font = Font(bold=True, color="111827")
        for c in range(1, len(device_columns) + 1):
            ws.cell(r, c).fill = GROUP_FILL
        r += 1
        for row in members:
            row = {**row, "status": DEVICE_STATUS_LABEL.get(row.get("status"), row.get("status"))}
            for c, (key, _) in enumerate(device_columns, 1):
                ws.cell(r, c, _csv_safe(_cell(row.get(key))))
            ws.row_dimensions[r].outline_level = 1  # se puede plegar cada departamento en Excel
            r += 1
    for c, (_, title) in enumerate(device_columns, 1):
        ws.column_dimensions[get_column_letter(c)].width = max(12, min(40, len(title) + 4))
    ws.sheet_properties.outlinePr.summaryBelow = False
    ws.freeze_panes = "B2"

    if after:
        after(wb, used)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
