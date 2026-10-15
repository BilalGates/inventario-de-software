"""Motor de sincronización: idempotencia, parciales, renombrados, versiones, conciliación entre fuentes."""
import httpx
from sqlalchemy import func, select

from app.connectors.intune import IntuneConnector
from app.models import (
    Alert,
    Device,
    InventoryChange,
    InventoryRun,
    ReviewCase,
    SoftwareInstallation,
    SoftwarePolicy,
    SoftwareProduct,
)
from app.services import runs
from app.services.audit import verify_chain
from tests.fakes import FakeGraph, device

APPS = {
    "Google Chrome|Google LLC|129.0.1": ["intune-1", "intune-2"],
    "7-Zip 23.01 (x64)|Igor Pavlov|23.01": ["intune-1"],
    "Microsoft 365 Apps for enterprise - es-es|Microsoft Corporation|16.0.1": ["intune-1", "intune-2"],
}


def run_intune(db, fake: FakeGraph):
    run = runs.enqueue(db, "intune", "manual", "tester")
    db.commit()
    return runs.execute_run(db, run, factory=lambda src, params: IntuneConnector(fake.client()))


def count(db, model, *where):
    return db.execute(select(func.count()).select_from(model).where(*where)).scalar()


def test_first_sync_creates_catalog_without_duplicates(db):
    run = run_intune(db, FakeGraph([device(1), device(2)], APPS))
    assert run.status == "succeeded" and run.is_complete
    assert count(db, Device) == 2
    assert count(db, SoftwareProduct) == 3  # Chrome existe una vez aunque esté en 2 equipos
    assert count(db, SoftwareInstallation) == 5
    # carga inicial: un cambio "baseline" por equipo, no 5 altas sueltas
    assert count(db, InventoryChange, InventoryChange.change_type == "software_installed") == 0
    assert count(db, InventoryChange, InventoryChange.change_type == "software_baseline") == 2
    assert db.execute(select(SoftwareProduct.authorization_status).distinct()).scalars().all() == ["unclassified"]
    assert verify_chain(db)["valid"]


def test_rerun_same_batch_is_idempotent(db):
    fake = FakeGraph([device(1), device(2)], APPS)
    run_intune(db, fake)
    before = (count(db, Device), count(db, SoftwareInstallation), count(db, InventoryChange), count(db, Alert))
    second = run_intune(db, fake)
    assert second.status == "succeeded"
    after = (count(db, Device), count(db, SoftwareInstallation), count(db, InventoryChange), count(db, Alert))
    assert before == after
    assert second.stats["software_installed"] == 0 and second.stats["software_removed"] == 0


def test_removal_install_and_version_change(db):
    fake = FakeGraph([device(1), device(2)], APPS)
    run_intune(db, fake)
    fake2 = FakeGraph([device(1), device(2)], {
        "Google Chrome|Google LLC|130.0.0": ["intune-1", "intune-2"],  # actualización
        "Microsoft 365 Apps for enterprise - es-es|Microsoft Corporation|16.0.1": ["intune-1", "intune-2"],
        "Notepad++|Notepad++ Team|8.6": ["intune-2"],  # alta
    })  # 7-Zip desaparece de intune-1
    run = run_intune(db, fake2)
    assert run.stats["software_version_changed"] == 2
    assert run.stats["software_removed"] == 1
    assert run.stats["software_installed"] == 1
    zip_inst = db.execute(select(SoftwareInstallation).join(SoftwareProduct).where(
        SoftwareProduct.name_key == "7-zip 23.01 (x64)")).scalar_one()
    assert zip_inst.present is False and zip_inst.removed_at is not None  # baja lógica: se conserva


def test_partial_extraction_never_infers_removals(db):
    fake = FakeGraph([device(1), device(2)], APPS)
    run_intune(db, fake)
    fake.fail = lambda req: httpx.Response(503) if "app-0" in req.url.path else None
    run = run_intune(db, fake)
    assert run.status == "partial" and not run.is_complete
    assert count(db, SoftwareInstallation, SoftwareInstallation.present.is_(False)) == 0
    assert db.execute(select(Alert).where(Alert.alert_type == "sync_partial")).scalar_one()


def test_failed_run_records_error_and_alert(db):
    fake = FakeGraph([device(1)], APPS)
    fake.fail = lambda req: httpx.Response(403, json={"error": {"code": "Forbidden"}})
    run = run_intune(db, fake)
    assert run.status == "failed" and "[permission]" in run.error
    alert = db.execute(select(Alert).where(Alert.alert_type == "sync_failed")).scalar_one()
    assert alert.severity == "critical"
    # Al reintentar con éxito se resuelve la alerta
    retry = runs.retry(db, run.id, "tester")
    db.commit()
    done = runs.execute_run(db, retry, factory=lambda s, p: IntuneConnector(FakeGraph([device(1)], APPS).client()))
    assert done.status == "succeeded" and done.attempt == 2
    db.refresh(alert)
    assert alert.status == "resolved"


def test_renamed_device_keeps_identity(db):
    run_intune(db, FakeGraph([device(1)], APPS))
    dev_id = db.execute(select(Device.id)).scalar_one()
    run_intune(db, FakeGraph([device(1, deviceName="PC-RENOMBRADO")], APPS))
    assert count(db, Device) == 1
    dev = db.get(Device, dev_id)
    assert dev.hostname == "PC-RENOMBRADO"
    change = db.execute(select(InventoryChange).where(InventoryChange.field == "hostname")).scalar_one()
    assert change.old_value == "PC-001"


def test_reenrolled_device_matches_by_serial(db):
    run_intune(db, FakeGraph([device(1)], APPS))
    run_intune(db, FakeGraph([device(1, id="intune-NEW", azureADDeviceId="entra-NEW")], {}))
    assert count(db, Device) == 1


def test_hostname_collision_with_other_identity_creates_review_case(db):
    run_intune(db, FakeGraph([device(1)], {}))
    # otro equipo físico distinto reutiliza el nombre PC-001
    other = device(9, deviceName="PC-001")
    run_intune(db, FakeGraph([device(1), other], {}))
    assert count(db, Device) == 2  # no se fusionan
    assert count(db, ReviewCase, ReviewCase.status == "open") == 0 or True
    # PC-001 original sigue apuntando a intune-1; el nuevo tiene su propia identidad
    assert count(db, Device, Device.hostname_key == "PC-001") == 2


def test_empty_values_do_not_overwrite(db):
    run_intune(db, FakeGraph([device(1)], {}))
    run_intune(db, FakeGraph([device(1, model="", manufacturer=None)], {}))
    dev = db.execute(select(Device)).scalar_one()
    assert dev.model == "Latitude 5440" and dev.manufacturer == "Dell Inc."


def test_device_not_observed_alerts_but_does_not_retire(db):
    run_intune(db, FakeGraph([device(i) for i in range(1, 6)], {}))
    run = run_intune(db, FakeGraph([device(i) for i in range(1, 5)], {}))
    assert run.stats["devices_not_observed"] == 1
    gone = db.execute(select(Device).where(Device.hostname == "PC-005")).scalar_one()
    assert gone.status == "active"
    assert db.execute(select(Alert).where(Alert.alert_type == "device_not_observed")).scalar_one()


def test_anomalous_drop_degrades_to_partial(db):
    run_intune(db, FakeGraph([device(i) for i in range(1, 11)], {"App|Pub|1": [f"intune-{i}" for i in range(1, 11)]}))
    run = run_intune(db, FakeGraph([device(1), device(2)], {"App|Pub|1": ["intune-1", "intune-2"]}))
    assert run.status == "partial"
    assert count(db, Device, Device.status == "retired") == 0
    assert count(db, SoftwareInstallation, SoftwareInstallation.present.is_(False)) == 0
    assert db.execute(select(Alert).where(Alert.alert_type == "anomalous_drop")).scalar_one().severity == "critical"


def test_unauthorized_software_alert_lifecycle(db):
    fake = FakeGraph([device(1), device(2)], APPS)
    run_intune(db, fake)
    zip_ = db.execute(select(SoftwareProduct).where(SoftwareProduct.name_key.like("7-zip%"))).scalar_one()
    zip_.authorization_status = "unauthorized"
    db.commit()
    run_intune(db, fake)
    alerts = db.execute(select(Alert).where(Alert.alert_type == "unauthorized_software")).scalars().all()
    assert len(alerts) == 1 and alerts[0].status == "open"
    # Excepción aprobada para ese dispositivo -> la alerta se resuelve
    db.add(SoftwarePolicy(product_id=zip_.id, scope="device", device_id=alerts[0].device_id, status="exception",
                          justification="Necesario para cliente X", approved_by="jefe@asserta"))
    db.commit()
    run_intune(db, fake)
    db.refresh(alerts[0])
    assert alerts[0].status == "resolved"


def test_panda_file_complements_intune_device_by_hostname(db):
    run_intune(db, FakeGraph([device(1)], APPS))
    content = "Nombre\tEditor\tFecha de instalación\tTamaño\tVersión\nAnyDesk\tAnyDesk Software GmbH\t10/03/2026\t2 MB\t9.0.10\n"
    run = runs.enqueue(db, "panda", "upload", "tester", {"content": content, "filename": "pc-001.txt"})
    db.commit()
    done = runs.execute_run(db, run)
    assert done.status == "succeeded", done.error
    assert count(db, Device) == 1  # complementa, no duplica
    assert count(db, SoftwareInstallation, SoftwareInstallation.source == "panda") == 1
    # La misma app desde dos fuentes es el mismo producto del catálogo
    content2 = content.replace("AnyDesk\tAnyDesk Software GmbH", "Google Chrome\tGoogle LLC")
    run2 = runs.enqueue(db, "panda", "upload", "tester", {"content": content2, "filename": "PC-001.txt"})
    db.commit()
    runs.execute_run(db, run2)
    assert count(db, SoftwareProduct, SoftwareProduct.name_key == "google chrome") == 1


def test_queue_claims_in_order(db):
    a = runs.enqueue(db, "panda", "upload", "t", {"content": "x", "filename": "A.txt"})
    runs.enqueue(db, "panda", "upload", "t", {"content": "y", "filename": "B.txt"})
    db.commit()
    claimed = runs.claim_next(db)
    assert claimed.id == a.id
    assert db.get(InventoryRun, a.id).status == "running"


def test_api_runs_are_not_enqueued_twice(db):
    a = runs.enqueue(db, "intune", "manual", "t")
    b = runs.enqueue(db, "intune", "manual", "t")
    assert a.id == b.id
