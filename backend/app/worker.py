"""Worker de inventario: proceso independiente de la web.

    python -m app.worker            # bucle continuo (servicio)
    python -m app.worker --once     # una pasada (útil para Programador de tareas / cron)

En cada pasada:
1. Recupera ejecuciones colgadas.
2. Programación mensual: si toca y no se ha lanzado este mes, encola las fuentes API.
3. Carpeta supervisada de Panda: encola cada fichero nuevo y lo mueve a processed/ o failed/.
4. Procesa la cola de ejecuciones.
5. Cuando las ejecuciones programadas del mes terminan, genera el BORRADOR del inventario
   mensual (la aprobación la hace IT desde la aplicación).
6. Alertas de fuentes sin sincronización reciente.
"""
from __future__ import annotations

import argparse
import logging
import shutil
import signal
import time
from pathlib import Path

from sqlalchemy import select

from app.connectors.files import decode, hostname_from_filename
from app.core.config import get_settings
from app.core.logging import setup_logging
from app.db import session_scope, utcnow
from app.models import AppSetting, InventoryRun, InventorySnapshot, InventorySource
from app.services import runs as run_service
from app.services import snapshots
from app.services.alerts import check_stale_sources
from app.services.bootstrap import ensure_reference_data, get_setting

log = logging.getLogger("inventario.worker")
_stop = False


def _handle_stop(*_):
    global _stop
    _stop = True


def schedule_due(db, now=None) -> list[str]:
    """Devuelve las fuentes a lanzar si la programación mensual está vencida y no se lanzó este mes."""
    now = now or utcnow()
    cfg = get_setting(db, "schedule.monthly") or {}
    if not cfg.get("enabled"):
        return []
    day, hour = int(cfg.get("day", 1)), int(cfg.get("hour", 6))
    if (now.day, now.hour) < (day, hour):
        return []
    period = now.strftime("%Y-%m")
    due = []
    for code in cfg.get("sources", []):
        src = db.execute(select(InventorySource).where(InventorySource.code == code,
                                                       InventorySource.enabled.is_(True))).scalar_one_or_none()
        if src is None:
            continue
        launched = db.execute(select(InventoryRun.id).where(
            InventoryRun.source_id == src.id, InventoryRun.trigger == "schedule", InventoryRun.period == period
        )).first()
        if not launched:
            due.append(code)
    return due


def maybe_generate_monthly_snapshot(db, now=None) -> InventorySnapshot | None:
    now = now or utcnow()
    period = now.strftime("%Y-%m")
    scheduled = db.execute(select(InventoryRun).where(InventoryRun.trigger.in_(("schedule", "retry")),
                                                      InventoryRun.period == period)).scalars().all()
    if not scheduled or any(r.status in run_service.ACTIVE for r in scheduled):
        return None
    flag = f"snapshot.auto.{period}"
    if db.get(AppSetting, flag) is not None:
        return None
    snap = snapshots.generate(db, period, "system:scheduler")
    db.add(AppSetting(key=flag, value={"snapshot_id": snap.id}, updated_by="system"))
    return snap


def scan_drop_dir(db, drop_dir: str) -> int:
    base = Path(drop_dir)
    if not drop_dir or not base.is_dir():
        return 0
    (base / "processed").mkdir(exist_ok=True)
    (base / "failed").mkdir(exist_ok=True)
    count = 0
    csvs = [p for p in sorted(base.glob("*.csv")) if not p.name.startswith("Errores_Inventario_Intune_")]
    for path in sorted(base.glob("*.txt")) + csvs:
        try:
            content = decode(path.read_bytes())
            if path.suffix.lower() == ".txt":
                if not hostname_from_filename(path.name):
                    raise ValueError("nombre de fichero sin hostname")
                run_service.enqueue(db, "panda", "watcher", "system:watcher",
                                    {"content": content, "filename": path.name})
            else:
                # Salida de Inventario_Programas_Intune.ps1: es completa si el script no dejó
                # su fichero de errores con la misma marca de tiempo.
                stamp = path.stem.removeprefix("Inventario_Programas_Intune_")
                is_script = stamp != path.stem
                errors = base / f"Errores_Inventario_Intune_{stamp}.csv"
                run_service.enqueue(db, "intune", "watcher", "system:watcher",
                                    {"content": content, "filename": path.name, "kind": "apps" if is_script else None,
                                     "declared_complete": is_script and not errors.exists()})
                if is_script and errors.exists():
                    shutil.move(str(errors), str(base / "processed" / f"{utcnow():%Y%m%d%H%M%S}_{errors.name}"))
            db.commit()
            target = base / "processed" / f"{utcnow():%Y%m%d%H%M%S}_{path.name}"
            count += 1
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            log.warning("Fichero %s rechazado: %s", path.name, exc)
            target = base / "failed" / path.name
        shutil.move(str(path), str(target))
    return count


def tick(settings=None) -> dict:
    settings = settings or get_settings()
    summary = {"enqueued": 0, "executed": 0, "files": 0, "snapshot": None}
    with session_scope() as db:
        ensure_reference_data(db)
        run_service.recover_stuck(db)
        for code in schedule_due(db):
            run_service.enqueue(db, code, "schedule", "system:scheduler")
            summary["enqueued"] += 1
        db.commit()
        summary["files"] = scan_drop_dir(db, settings.panda_drop_dir)
        if settings.intune_drop_dir:
            summary["files"] += scan_drop_dir(db, settings.intune_drop_dir)
    while not _stop:
        with session_scope() as db:
            run = run_service.claim_next(db)
            if run is None:
                break
            log.info("Ejecutando run %s", run.id)
            done = run_service.execute_run(db, run)
            log.info("Run %s -> %s", done.id, done.status)
            summary["executed"] += 1
    with session_scope() as db:
        snap = maybe_generate_monthly_snapshot(db)
        summary["snapshot"] = snap.id if snap else None
        check_stale_sources(db, int(get_setting(db, "alerts.stale_source_days") or 3))
        hb = db.get(AppSetting, "worker.heartbeat") or AppSetting(key="worker.heartbeat")
        hb.value, hb.updated_by = {"at": utcnow().isoformat(timespec="seconds"), **summary}, "system:worker"
        db.add(hb)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Worker de Inventario Asserta")
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    setup_logging()
    settings = get_settings()
    signal.signal(signal.SIGINT, _handle_stop)
    signal.signal(signal.SIGTERM, _handle_stop)
    log.info("Worker iniciado (entorno=%s)", settings.environment)
    while not _stop:
        try:
            summary = tick(settings)
            if any(summary.values()):
                log.info("Pasada: %s", summary)
        except Exception:  # noqa: BLE001 - el servicio no debe morir por un error puntual
            log.exception("Error en la pasada del worker")
        if args.once:
            break
        for _ in range(settings.worker_poll_seconds):
            if _stop:
                break
            time.sleep(1)


if __name__ == "__main__":
    main()
