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
