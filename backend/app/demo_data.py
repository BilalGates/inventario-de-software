"""Datos de demostración SINTÉTICOS para desarrollo y pruebas de interfaz.

    python -m app.demo_data

No contiene datos reales. Usa el pipeline auténtico: genera ficheros CSV con el formato de
exportación de Intune y exportaciones de Panda, y los procesa con los mismos conectores y el
mismo motor de sincronización que en producción (dos "meses" para tener histórico y cambios).
Se niega a ejecutarse en producción.
"""
from __future__ import annotations

import csv
import io
import random

from sqlalchemy import select

from app.core.config import get_settings
from app.db import Base, get_engine, session_scope
from app.models import Department, Device, SoftwareProduct
from app.services import runs, snapshots
from app.services.bootstrap import ensure_reference_data
from app.services.devices import reassign

DEPTS = [("it", "IT", "Sistemas y soporte"), ("gerencia", "Gerencia", "Dirección general"),
         ("silicon", "Silicon", "Desarrollo de producto"), ("data_science", "Data Science/Analytics", "Analítica"),
         ("administracion", "Administración", "Finanzas y RR. HH.")]
COMMON = [("Google Chrome", "Google LLC", ["129.0.6668.90", "130.0.6723.59"]),
          ("Microsoft 365 Apps for enterprise - es-es", "Microsoft Corporation", ["16.0.17928.20156"]),
          ("Microsoft Teams", "Microsoft Corporation", ["24215.1007.3082.1590"]),
          ("Adobe Acrobat Reader (64-bit)", "Adobe", ["24.003.20112", "24.004.20219"]),
          ("7-Zip 23.01 (x64)", "Igor Pavlov", ["23.01"]),
          ("Microsoft Visual C++ 2015-2022 Redistributable (x64) - 14.40.33810", "Microsoft Corporation", ["14.40.33810.0"]),
          ("Intel(R) Serial IO Driver", "Intel Corporation", ["30.100.2237.26"]),
          ("Panda Endpoint Agent", "Panda Security", ["8.21.00.0001"])]
BY_DEPT = {"it": [("Wireshark 4.2.5 x64", "The Wireshark developer community", ["4.2.5"]),
                  ("PuTTY release 0.81 (64-bit)", "Simon Tatham", ["0.81.0.0"]),
                  ("Visual Studio Code", "Microsoft Corporation", ["1.94.2"])],
           "data_science": [("Python 3.12.4 (64-bit)", "Python Software Foundation", ["3.12.4150.0"]),
                            ("Anaconda3 2024.06-1 (Python 3.12.4 64-bit)", "Anaconda, Inc.", ["2024.06-1"]),
                            ("Tableau Desktop 2024.2", "Tableau Software", ["24.2.1035"])],
           "silicon": [("KiCad 8.0.4", "KiCad", ["8.0.4"]), ("Visual Studio Code", "Microsoft Corporation", ["1.94.2"])],
           "administracion": [("A3ERP", "Wolters Kluwer", ["13.2.0"])], "gerencia": []}
RISKY = [("AnyDesk", "AnyDesk Software GmbH", ["9.0.10"]), ("uTorrent", "BitTorrent Inc.", ["3.6.0"])]


def _devices_csv(devs: list[dict]) -> str:
    buf = io.StringIO()
    cols = ["Device ID", "Device name", "Serial number", "AzureADDeviceId", "Manufacturer", "Model", "OS", "OS version",
            "UserPrincipalName", "UserDisplayName", "PhysicalMemoryInBytes", "TotalStorageSpaceInBytes",
            "FreeStorageSpaceInBytes", "IsEncrypted", "ComplianceState", "Last check-in", "EnrolledDateTime"]
    w = csv.DictWriter(buf, fieldnames=cols)
    w.writeheader()
    for d in devs:
        w.writerow({"Device ID": d["id"], "Device name": d["name"], "Serial number": d["serial"],
                    "AzureADDeviceId": d["entra"], "Manufacturer": d["mfr"], "Model": d["model"], "OS": "Windows",
                    "OS version": d["os"], "UserPrincipalName": d["upn"], "UserDisplayName": d["user"],
                    "PhysicalMemoryInBytes": d["ram"], "TotalStorageSpaceInBytes": d["disk"],
                    "FreeStorageSpaceInBytes": d["disk"] // 3, "IsEncrypted": d["enc"], "ComplianceState": d["comp"],
                    "Last check-in": "2026-10-14 08:00:00", "EnrolledDateTime": "2025-02-01 09:00:00"})
    return buf.getvalue()


def _apps_csv(rows: list[tuple]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["DeviceId", "DeviceName", "AppName", "Publisher", "Version", "Platform"])
    w.writerows(rows)
    return buf.getvalue()


def main() -> None:
    if get_settings().environment == "production":
        raise SystemExit("Los datos de demostración no pueden cargarse en producción.")
    rnd = random.Random(42)
    Base.metadata.create_all(get_engine())
    with session_scope() as db:
        ensure_reference_data(db)
        if db.execute(select(Device)).first():
            raise SystemExit("La base de datos ya tiene dispositivos; use una BD vacía para la demo.")
        depts = {}
        for code, name, desc in DEPTS:
            dep = Department(code=code, name=name, description=desc)
            db.add(dep)
            db.flush()
            depts[code] = dep
        devs = []
        n = 0
        for code, count in (("it", 5), ("gerencia", 3), ("silicon", 8), ("data_science", 6), ("administracion", 5)):
            for _ in range(count):
                n += 1
                mfr, model = rnd.choice([("Dell Inc.", "Latitude 5440"), ("LENOVO", "ThinkPad T14 Gen 4"),
                                         ("HP", "EliteBook 840 G10"), ("Dell Inc.", "OptiPlex 7010")])
                devs.append({"id": f"demo-{n:04d}", "name": f"DEMO-{code[:3].upper()}-{n:02d}", "serial": f"DEMO{n:06d}",
                             "entra": f"00000000-demo-0000-0000-{n:012d}", "mfr": mfr, "model": model,
                             "os": rnd.choice(["10.0.22631.4317", "10.0.22631.4391", "10.0.26100.2033"]),
                             "upn": f"usuario{n:02d}@demo.invalid", "user": f"Usuario Demo {n:02d}",
                             "ram": rnd.choice([16, 32]) * 1024**3, "disk": rnd.choice([256, 512, 1024]) * 1000**3,
                             "enc": rnd.random() > 0.1, "comp": "compliant" if rnd.random() > 0.15 else "noncompliant",
                             "dept": code})
        db.commit()

        def apps_for(month: int) -> list[tuple]:
            rows = []
            for d in devs:
                for name, pub, vers in COMMON + BY_DEPT[d["dept"]]:
                    rows.append((d["id"], d["name"], name, pub, vers[min(month, len(vers) - 1)], "Windows"))
                if d["dept"] in ("silicon", "it") and rnd.random() < 0.25:
                    name, pub, vers = rnd.choice(RISKY)
                    rows.append((d["id"], d["name"], name, pub, vers[0], "Windows"))
            if month == 1:  # el segundo mes desaparece 7-Zip de un par de equipos
                rows = [r for r in rows if not (r[2].startswith("7-Zip") and r[0] in ("demo-0003", "demo-0010"))]
            return rows

        for month, period in ((0, "2026-09"), (1, "2026-10")):
            for params in ({"content": _devices_csv(devs), "filename": "intune_devices_demo.csv"},
                           {"content": _apps_csv(apps_for(month)), "filename": "intune_apps_demo.csv",
                            "declared_complete": True}):
                run = runs.enqueue(db, "intune", "upload", "demo", params, period=period)
                db.commit()
                done = runs.execute_run(db, run)
                print(f"{period} {params['filename']}: {done.status} {done.error or ''}")
            if month == 0:
                for d in devs:
                    dev = db.execute(select(Device).where(Device.hostname == d["name"])).scalar_one()
                    reassign(db, dev, department_id=depts[d["dept"]].id, reason="Carga de demostración", actor="demo")
                db.commit()
                snap = snapshots.generate(db, period, "demo")
                snapshots.review(db, snap.id, "demo", True, "Demo: Intune vía CSV", accept_incomplete=True)
                db.commit()
        # Clasificación inicial del catálogo de demo
        for p in db.execute(select(SoftwareProduct)).scalars():
            if p.name.startswith(("Google Chrome", "Microsoft", "Adobe", "7-Zip", "Panda")):
                p.authorization_status = "authorized"
            elif p.name.startswith("uTorrent"):
                p.authorization_status = "unauthorized"
        db.commit()
        from app.services.alerts import evaluate_unauthorized

        evaluate_unauthorized(db)
        # Un servidor manual y una exportación de Panda de ejemplo
        srv = Device(hostname="DEMO-SRV-01", hostname_key="DEMO-SRV-01", serial_number="DEMOSRV0001",
                     manufacturer="HPE", model="ProLiant DL380 Gen10", os_name="Windows Server 2022", status="active",
                     location="CPD", field_sources={})
        db.add(srv)
        db.flush()
        reassign(db, srv, department_id=depts["it"].id, reason="Alta manual de demostración", actor="demo")
        db.commit()
        panda = ("Nombre\tEditor\tFecha de instalación\tTamaño\tVersión\n"
                 "Veeam Backup & Replication\tVeeam Software Group GmbH\t01/06/2026\t1,2 GB\t12.1.2.172\n"
                 "Microsoft SQL Server 2022 (64-bit)\tMicrosoft Corporation\t02/06/2026\t-\t16.0.1000.6\n")
        run = runs.enqueue(db, "panda", "upload", "demo", {"content": panda, "filename": "DEMO-SRV-01.txt"})
        db.commit()
        print("Panda DEMO-SRV-01:", runs.execute_run(db, run).status)


if __name__ == "__main__":
    main()
