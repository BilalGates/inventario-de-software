from datetime import datetime

from sqlalchemy import select

from app import worker
from app.models import AppSetting, InventorySnapshot
from app.services import runs

PANDA = "Nombre\tEditor\tFecha de instalación\tTamaño\tVersión\nAnyDesk\tAnyDesk\t10/03/2026\t2 MB\t9.0\n"


def test_schedule_due_once_per_month(db):
    db.get(AppSetting, "schedule.monthly").value = {"enabled": True, "day": 5, "hour": 6, "sources": ["intune"]}
    db.commit()
    assert worker.schedule_due(db, datetime(2026, 10, 4, 23)) == []
    assert worker.schedule_due(db, datetime(2026, 10, 5, 6)) == ["intune"]
    runs.enqueue(db, "intune", "schedule", "system", period="2026-10")
    db.commit()
    assert worker.schedule_due(db, datetime(2026, 10, 20, 6)) == []  # ya lanzado este mes
    assert worker.schedule_due(db, datetime(2026, 11, 5, 7)) == ["intune"]


def test_schedule_disabled(db):
    db.get(AppSetting, "schedule.monthly").value = {"enabled": False, "day": 1, "hour": 0, "sources": ["intune"]}
    db.commit()
    assert worker.schedule_due(db, datetime(2026, 10, 15)) == []


def test_monthly_snapshot_waits_for_runs_and_is_generated_once(db):
    now = datetime(2026, 10, 2, 7)
    run = runs.enqueue(db, "intune", "schedule", "system", period="2026-10")
    db.commit()
    assert worker.maybe_generate_monthly_snapshot(db, now) is None  # aún en cola
    run.status = "failed"
    db.commit()
    snap = worker.maybe_generate_monthly_snapshot(db, now)
    assert snap is not None and snap.status == "draft" and snap.is_complete is False
    db.commit()
    assert worker.maybe_generate_monthly_snapshot(db, now) is None
    assert len(db.execute(select(InventorySnapshot)).scalars().all()) == 1


SCRIPT_CSV = ('"Equipo";"Usuario";"Programa";"Version";"Editor";"PlataformaApp";"SistemaOperativo";"VersionSO";'
              '"UltimaSincronizacion";"AzureADDeviceId";"IntuneDeviceId"\n'
              '"PC-01";"ana@asserta.es";"Google Chrome";"130.0";"Google LLC";"windows";"Windows";"10.0.22631";'
              '"10/14/2026 8:00:00 AM";"aad-1";"int-1"\n'
              '"PC-01";"ana@asserta.es";"7-Zip 23.01 (x64)";"23.01";"Igor Pavlov";"windows";"Windows";"10.0.22631";'
              '"10/14/2026 8:00:00 AM";"aad-1";"int-1"\n')


def test_intune_script_csv_uploaded_from_the_web(db):
    """Contingencia: el CSV de tools/Inventario_Programas_Intune.ps1 se sube desde Sincronización."""
    from app.connectors.files import decode
    from app.models import Device, SoftwareInstallation

    raw = ("﻿" + SCRIPT_CSV).encode("utf-8")  # el script lo guarda con BOM, como lo recibe la subida
    runs.enqueue(db, "intune", "upload", "it@asserta.test",
                 {"content": decode(raw), "filename": "Inventario_Programas_Intune_2026-10-15_09-00-00.csv",
                  "declared_complete": True})
    db.commit()
    run = runs.claim_next(db)
    done = runs.execute_run(db, run)
    assert done.status == "succeeded", done.error
    dev = db.execute(select(Device)).scalar_one()
    assert dev.hostname == "PC-01" and dev.primary_user.upn == "ana@asserta.es" and dev.os_version == "10.0.22631"
    assert {e.id_type for e in dev.external_ids} == {"intune_device_id", "entra_device_id"}
    assert len(db.execute(select(SoftwareInstallation)).scalars().all()) == 2
