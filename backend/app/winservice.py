"""Servicio de Windows "InventarioAsserta" (requiere pywin32).

Diseño: este proceso solo habla con el Administrador de servicios de Windows. La aplicación
(app.server) se ejecuta en un PROCESO HIJO con el Python del .venv, aislada de las librerías
globales del Python base. El hijo se asocia a un Job Object, de modo que al parar el servicio
(o si este muere) Windows cierra también la aplicación y cualquier subproceso.

Instalación: deploy/windows/install-service.ps1 (como administrador).
Gestión manual:  python -m app.winservice install|start|stop|remove
"""
from __future__ import annotations

import os
import site
import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
VENV_PYTHON = BACKEND / ".venv" / "Scripts" / "python.exe"
SERVICE_DIR = Path(os.environ.get("ProgramData", r"C:\ProgramData")) / "InventarioAsserta"
LOG_DIR = SERVICE_DIR / "logs"

# Aquí solo se usan las extensiones de pywin32 del .venv; el resto de librerías las carga el
# proceso hijo con su propio intérprete.
site.addsitedir(str(BACKEND / ".venv" / "Lib" / "site-packages"))

import servicemanager  # noqa: E402
import win32api  # noqa: E402
import win32con  # noqa: E402
import win32event  # noqa: E402
import win32job  # noqa: E402
import win32service  # noqa: E402
import win32serviceutil  # noqa: E402


class InventarioService(win32serviceutil.ServiceFramework):
    _svc_name_ = "InventarioAsserta"
    _svc_display_name_ = "Inventario Asserta"
    _svc_description_ = "Inventario IT de Asserta: interfaz web en http://127.0.0.1:8080 y sincronizaciones programadas."
    # Lo aloja el python.exe BASE (junto a su DLL); el pythonservice.exe que pywin32 copia al
    # .venv no encuentra python3xx.dll.
    _exe_name_ = getattr(sys, "_base_executable", sys.executable)
    _exe_args_ = f'"{Path(__file__).resolve()}"'

    def __init__(self, args):
        super().__init__(args)
        self.stop_event = win32event.CreateEvent(None, 0, 0, None)
        self.proc: subprocess.Popen | None = None
        self.job = None

    def SvcStop(self):  # noqa: N802 - API de pywin32
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.stop_event)

    def _start_child(self) -> None:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        out = open(LOG_DIR / "app-output.log", "ab")  # salida y tracebacks de arranque
        env = {**os.environ, "INV_LOG_FILE": str(LOG_DIR / "service.log"), "PYTHONNOUSERSITE": "1",
               "PYTHONUNBUFFERED": "1"}
        self.proc = subprocess.Popen([str(VENV_PYTHON), "-m", "app.server"], cwd=str(BACKEND), env=env,
                                     stdout=out, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                     creationflags=subprocess.CREATE_NO_WINDOW)
        # Job Object: al cerrarlo, Windows termina el hijo y sus subprocesos (el python.exe del
        # .venv es un lanzador que crea a su vez el intérprete real).
        self.job = win32job.CreateJobObject(None, "")
        info = win32job.QueryInformationJobObject(self.job, win32job.JobObjectExtendedLimitInformation)
        info["BasicLimitInformation"]["LimitFlags"] = win32job.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        win32job.SetInformationJobObject(self.job, win32job.JobObjectExtendedLimitInformation, info)
        handle = win32api.OpenProcess(win32con.PROCESS_SET_QUOTA | win32con.PROCESS_TERMINATE, False, self.proc.pid)
        win32job.AssignProcessToJobObject(self.job, handle)

    def SvcDoRun(self):  # noqa: N802
        servicemanager.LogInfoMsg("Inventario Asserta: iniciando")
        try:
            self._start_child()
        except Exception as exc:  # noqa: BLE001
            servicemanager.LogErrorMsg(f"Inventario Asserta no pudo lanzar la aplicación: {exc}")
            os._exit(1)
        failed = False
        # Espera la orden de parada; si la aplicación cae, el servicio termina con error y
        # Windows aplica la política de reinicio configurada.
        while win32event.WaitForSingleObject(self.stop_event, 2000) == win32event.WAIT_TIMEOUT:
            if self.proc.poll() is not None:
                failed = True
                servicemanager.LogErrorMsg(
                    f"La aplicación terminó con código {self.proc.returncode}. Ver {LOG_DIR}\\app-output.log")
                break
        if self.proc.poll() is None:
            self.proc.terminate()
        win32api.CloseHandle(self.job)  # termina también cualquier subproceso
        servicemanager.LogInfoMsg("Inventario Asserta: detenido")
        if failed:
            os._exit(1)  # salida con error para que actúe el reinicio automático


if __name__ == "__main__":
    if len(sys.argv) == 1:
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(InventarioService)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        win32serviceutil.HandleCommandLine(InventarioService)
