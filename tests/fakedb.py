"""
Dobles de prueba (fakes) para testear la lógica de negocio sin MySQL.

La lógica en `modules/` usa el patrón `db.execute(text(sql), params)` de SQLAlchemy
y consume el resultado con `.mappings().first()/.all()`, `.scalar()`, `.lastrowid`
y `.rowcount`. Estos fakes imitan esa interfaz lo justo para los tests.
"""
from __future__ import annotations

from typing import Any, Callable


class FakeResult:
    """Imita el objeto Result de SQLAlchemy en lo que usan los módulos."""

    def __init__(self, rows: list[dict] | None = None, lastrowid: int = 0, scalar: Any = None):
        self._rows = rows if rows is not None else []
        self.lastrowid = lastrowid
        self.rowcount = len(self._rows)
        self._scalar = scalar

    # .mappings() devuelve un objeto con .first()/.all(); aquí somos ese objeto.
    def mappings(self) -> "FakeResult":
        return self

    def first(self) -> dict | None:
        return self._rows[0] if self._rows else None

    def all(self) -> list[dict]:
        return list(self._rows)

    def scalar(self) -> Any:
        return self._scalar


class RecordingDB:
    """
    Conexión falsa que registra todo el SQL ejecutado.

    `responder(sql, params) -> FakeResult | None` permite devolver resultados
    a medida según la consulta. Si devuelve None se usan respuestas por defecto.
    """

    def __init__(self, responder: Callable[[str, dict], FakeResult | None] | None = None):
        self.executed: list[tuple[str, dict]] = []
        self._responder = responder
        self._auto_id = 0

    def execute(self, clause: Any, params: dict | None = None) -> FakeResult:
        sql = str(clause)
        params = dict(params or {})
        self.executed.append((sql, params))

        if self._responder is not None:
            result = self._responder(sql, params)
            if result is not None:
                return result

        head = sql.strip().upper()
        if head.startswith("INSERT"):
            self._auto_id += 1
            return FakeResult(lastrowid=self._auto_id)
        return FakeResult(rows=[])

    # --- helpers de aserción -------------------------------------------------

    def executed_sql(self) -> list[str]:
        return [sql for sql, _ in self.executed]

    def any_sql_contains(self, *needles: str) -> bool:
        upper = " ".join(self.executed_sql()).upper()
        return all(needle.upper() in upper for needle in needles)
