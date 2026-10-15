from datetime import datetime

from sqlalchemy import select

from app import worker
from app.models import AppSetting, InventoryRun, InventorySnapshot
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


def test_drop_folder_ingests_and_moves_files(db, tmp_path):
    (tmp_path / "PC-001.txt").write_text(PANDA, encoding="utf-8")
    (tmp_path / "notes.txt").write_text("", encoding="utf-8")  # sin contenido válido: se encola y fallará
    assert worker.scan_drop_dir(db, str(tmp_path)) == 2
    assert sorted(p.name.split("_", 1)[1] for p in (tmp_path / "processed").iterdir()) == ["PC-001.txt", "notes.txt"]
    assert not list(tmp_path.glob("*.txt"))
    queued = db.execute(select(InventoryRun).where(InventoryRun.trigger == "watcher")).scalars().all()
    assert len(queued) == 2


SCRIPT_CSV = ('"Equipo";"Usuario";"Programa";"Version";"Editor";"PlataformaApp";"SistemaOperativo";"VersionSO";'
              '"UltimaSincronizacion";"AzureADDeviceId";"IntuneDeviceId"\n'
              '"PC-01";"ana@asserta.es";"Google Chrome";"130.0";"Google LLC";"windows";"Windows";"10.0.22631";'
              '"10/14/2026 8:00:00 AM";"aad-1";"int-1"\n'
              '"PC-01";"ana@asserta.es";"7-Zip 23.01 (x64)";"23.01";"Igor Pavlov";"windows";"Windows";"10.0.22631";'
              '"10/14/2026 8:00:00 AM";"aad-1";"int-1"\n')


def test_intune_script_csv_is_imported_from_folder(db, tmp_path):
    from app.models import Device, SoftwareInstallation

    (tmp_path / "Inventario_Programas_Intune_2026-10-15_09-00-00.csv").write_text("﻿" + SCRIPT_CSV, encoding="utf-8")
    assert worker.scan_drop_dir(db, str(tmp_path)) == 1
    run = runs.claim_next(db)
    assert run.params["declared_complete"] is True
    done = runs.execute_run(db, run)
    assert done.status == "succeeded", done.error
    dev = db.execute(select(Device)).scalar_one()
    assert dev.hostname == "PC-01" and dev.primary_user.upn == "ana@asserta.es" and dev.os_version == "10.0.22631"
    assert {e.id_type for e in dev.external_ids} == {"intune_device_id", "entra_device_id"}
    assert len(db.execute(select(SoftwareInstallation)).scalars().all()) == 2


def test_intune_script_with_errors_file_is_not_complete(db, tmp_path):
    (tmp_path / "Inventario_Programas_Intune_2026-10-15_09-00-00.csv").write_text(SCRIPT_CSV, encoding="utf-8")
    (tmp_path / "Errores_Inventario_Intune_2026-10-15_09-00-00.csv").write_text("x", encoding="utf-8")
    assert worker.scan_drop_dir(db, str(tmp_path)) == 1
    assert runs.claim_next(db).params["declared_complete"] is False
