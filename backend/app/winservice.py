"""Servicio de Windows "InventarioAsserta" (requiere pywin32).

Instalación: deploy/windows/install-service.ps1 (como administrador).
Gestión manual:  python -m app.winservice install|start|stop|remove
"""
from __future__ import annotations

import site
import sys
import threading
from pathlib import Path

# El host de servicios (pythonservice.exe) no activa el entorno virtual: se añade a mano,
# junto con la carpeta del backend, antes de importar nada más.
BACKEND = Path(__file__).resolve().parents[1]
_venv_site = BACKEND / ".venv" / "Lib" / "site-packages"
if _venv_site.is_dir():
    site.addsitedir(str(_venv_site))
sys.path.insert(0, str(BACKEND))

import servicemanager  # noqa: E402
import win32event  # noqa: E402
import win32service  # noqa: E402
import win32serviceutil  # noqa: E402


class InventarioService(win32serviceutil.ServiceFramework):
    _svc_name_ = "InventarioAsserta"
    _svc_display_name_ = "Inventario Asserta"
    _svc_description_ = "Inventario IT de Asserta: interfaz web en http://127.0.0.1:8080 y sincronizaciones programadas."

    def __init__(self, args):
        super().__init__(args)
        self.stop_event = win32event.CreateEvent(None, 0, 0, None)
        self.server = None

    def SvcStop(self):  # noqa: N802 - API de pywin32
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        if self.server:
            self.server.stop()
        win32event.SetEvent(self.stop_event)

    def SvcDoRun(self):  # noqa: N802
        from app.server import InventoryServer

        servicemanager.LogInfoMsg("Inventario Asserta: iniciando")
        self.server = InventoryServer()
        thread = threading.Thread(target=self.server.run, daemon=True)
        thread.start()
        win32event.WaitForSingleObject(self.stop_event, win32event.INFINITE)
        thread.join(timeout=30)
        servicemanager.LogInfoMsg("Inventario Asserta: detenido")


if __name__ == "__main__":
    if len(sys.argv) == 1:
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(InventarioService)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        win32serviceutil.HandleCommandLine(InventarioService)
