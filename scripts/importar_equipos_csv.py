from __future__ import annotations

import argparse
import math
import sys
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from database.connection import get_engine
from utils.normalizer import normalize_equipo_nombre


DEFAULT_CSV = ROOT / "Inventario Equipos Informaticos Asserta(Equipos Asserta).csv"

DEPARTAMENTO_ALIASES = {
    "Data Science": "Data Science / Analytics",
    "Data Science ": "Data Science / Analytics",
    "Administrativo": "Administración",
}

CSV_TO_DB = {
    "Tipo de Dispositivo": "tipo_dispositivo",
    "Marca / Modelo": "marca_modelo",
    "Nº de Serie BIOS": "num_serie",
    "Dirección MAC": "mac_address",
    "Sistema Operativo": "sistema_operativo",
    "Procesador": "procesador",
    "Memoria RAM": "ram",
    "Almacenamiento": "almacenamiento",
    "Responsable": "responsable",
    "Ubicación Física": "ubicacion",
}


def clean_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    text_value = str(value).strip()
    return text_value or None


def clean_department(value: Any) -> str | None:
    department = clean_text(value)
    if not department:
        return None
    return DEPARTAMENTO_ALIASES.get(department, department)


def parse_cost(value: Any) -> Decimal | None:
    raw = clean_text(value)
    if not raw:
        return None
    raw = raw.replace("€", "").replace(".", "").replace(",", ".").strip()
    try:
        return Decimal(raw)
    except InvalidOperation:
        return None


def parse_date(value: Any):
    raw = clean_text(value)
    if not raw:
        return None
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def parse_active(value: Any) -> bool:
    return (clean_text(value) or "").casefold() == "activo"


def parse_bool_flag(value: Any) -> bool:
    return (clean_text(value) or "").casefold() in {
        "sí",
        "si",
        "yes",
        "true",
        "1",
        "servidor",
        "server",
    }


def is_empty_row(row: pd.Series) -> bool:
    return all(clean_text(value) is None for value in row.values)


def load_departments(db) -> dict[str, int]:
    rows = db.execute(text("SELECT id, nombre FROM departamentos")).mappings().all()
    return {row["nombre"].strip().casefold(): row["id"] for row in rows}


def find_equipo(db, nombre_norm: str, departamento_id: int | None = None) -> dict | None:
    query = "SELECT id, departamento_id FROM equipos WHERE nombre_norm = :nombre_norm"
    params: dict = {"nombre_norm": nombre_norm}
    if departamento_id is not None:
        query += " AND departamento_id = :departamento_id"
        params["departamento_id"] = departamento_id
    query += " LIMIT 1"
    row = db.execute(text(query), params).mappings().first()
    return dict(row) if row else None


def build_payload(row: pd.Series, departamento_id: int) -> dict:
    nombre = clean_text(row.get("Nombre del Equipo"))
    if not nombre:
        raise ValueError("Nombre del Equipo vacío")
    payload = {
        "departamento_id": departamento_id,
        "nombre": nombre,
        "nombre_norm": normalize_equipo_nombre(nombre),
        "activo": parse_active(row.get("Estado")),
        "coste": parse_cost(row.get("Coste")),
        "fecha_adquisicion": parse_date(row.get("Fecha de Adquisición")),
    }
    for csv_col, db_col in CSV_TO_DB.items():
        payload[db_col] = clean_text(row.get(csv_col))
    payload["es_servidor"] = parse_bool_flag(
        row.get("Es Servidor") or row.get("Servidor") or row.get("Tipo")
    )
    responsable = payload.get("responsable")
    payload["notas"] = responsable
    return payload


def upsert_equipo(db, payload: dict) -> str:
    existing = find_equipo(
        db,
        payload["nombre_norm"],
        departamento_id=payload["departamento_id"],
    )
    if existing:
        db.execute(
            text(
                """
                UPDATE equipos
                SET departamento_id = :departamento_id,
                    nombre = :nombre,
                    activo = :activo,
                    notas = COALESCE(:notas, notas),
                    tipo_dispositivo = :tipo_dispositivo,
                    marca_modelo = :marca_modelo,
                    num_serie = :num_serie,
                    mac_address = :mac_address,
                    sistema_operativo = :sistema_operativo,
                    procesador = :procesador,
                    ram = :ram,
                    almacenamiento = :almacenamiento,
                    responsable = :responsable,
                    ubicacion = :ubicacion,
                    coste = :coste,
                    fecha_adquisicion = :fecha_adquisicion,
                    es_servidor = :es_servidor,
                    fecha_baja = CASE WHEN :activo = TRUE THEN NULL ELSE fecha_baja END
                WHERE id = :id
                """
            ),
            {**payload, "id": existing["id"]},
        )
        return "updated"
    db.execute(
        text(
            """
            INSERT INTO equipos (
                departamento_id, nombre, nombre_norm, activo, notas,
                tipo_dispositivo, marca_modelo, num_serie, mac_address,
                sistema_operativo, procesador, ram, almacenamiento,
                responsable, ubicacion, coste, fecha_adquisicion, es_servidor
            )
            VALUES (
                :departamento_id, :nombre, :nombre_norm, :activo, :notas,
                :tipo_dispositivo, :marca_modelo, :num_serie, :mac_address,
                :sistema_operativo, :procesador, :ram, :almacenamiento,
                :responsable, :ubicacion, :coste, :fecha_adquisicion, :es_servidor
            )
            """
        ),
        payload,
    )
    return "inserted"


def import_csv(path: Path) -> dict[str, int]:
    df = pd.read_csv(path, sep=";", encoding="utf-8-sig", dtype=str)
    counters = {"inserted": 0, "updated": 0, "empty": 0, "incomplete": 0}
    engine = get_engine()
    with engine.begin() as db:
        departments = load_departments(db)
        for _, row in df.iterrows():
            if is_empty_row(row):
                counters["empty"] += 1
                continue
            nombre = clean_text(row.get("Nombre del Equipo"))
            departamento = clean_department(row.get("Departamento"))
            if not nombre or not departamento:
                counters["incomplete"] += 1
                continue
            departamento_id = departments.get(departamento.casefold())
            if not departamento_id:
                print(f"Departamento no encontrado para equipo {nombre}: {departamento}")
                counters["incomplete"] += 1
                continue
            payload = build_payload(row, departamento_id)
            if departamento.strip().casefold() == "servidores":
                payload["es_servidor"] = True
            result = upsert_equipo(db, payload)
            counters[result] += 1
    return counters


def main() -> int:
    parser = argparse.ArgumentParser(description="Importa el inventario hardware de equipos desde CSV.")
    parser.add_argument("--file", default=str(DEFAULT_CSV), help="Ruta al CSV de inventario de equipos.")
    args = parser.parse_args()
    path = Path(args.file).expanduser().resolve()
    if not path.exists():
        print(f"No existe el CSV: {path}", file=sys.stderr)
        return 1
    counters = import_csv(path)
    print("=== Importación de equipos completada ===")
    print(f"Insertados: {counters['inserted']}")
    print(f"Actualizados: {counters['updated']}")
    print(f"Filas vacías ignoradas: {counters['empty']}")
    print(f"Filas incompletas ignoradas: {counters['incomplete']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
