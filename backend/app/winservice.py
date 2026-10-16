"""Servicio de Windows "InventarioAsserta" (requiere pywin32).

Instalación: deploy/windows/install-service.ps1 (como administrador).
Gestión manual:  python -m app.winservice install|start|stop|remove
"""
from __future__ import annotations

import site
import sys
import threading
from pathlib import Path

# El servicio lo ejecuta el python.exe base, que no activa el entorno virtual: se añade a mano,
# junto con la carpeta del backend, antes de importar nada más.
BACKEND = Path(__file__).resolve().parents[1]
_venv = BACKEND / ".venv"
if (_venv / "Lib" / "site-packages").is_dir():
    site.addsitedir(str(_venv / "Lib" / "site-packages"))  # procesa también los .pth de pywin32
    # Las librerías del .venv deben ir ANTES que las globales del Python base: si no, se
    # mezclan versiones (p. ej. pydantic_core) y el proceso cae sin dejar rastro.
    _ours = [p for p in sys.path if str(_venv).lower() in p.lower()]
    sys.path[:] = _ours + [p for p in sys.path if p not in _ours and "site-packages" not in p.lower()]
sys.path.insert(0, str(BACKEND))

import servicemanager  # noqa: E402
import win32event  # noqa: E402
import win32service  # noqa: E402
import win32serviceutil  # noqa: E402


class InventarioService(win32serviceutil.ServiceFramework):
    _svc_name_ = "InventarioAsserta"
    _svc_display_name_ = "Inventario Asserta"
    _svc_description_ = "Inventario IT de Asserta: interfaz web en http://127.0.0.1:8080 y sincronizaciones programadas."
    # Lo ejecuta el python.exe BASE (que tiene python3xx.dll al lado) con este script; el
    # pythonservice.exe que pywin32 copia al .venv no encuentra la DLL y no llega a arrancar.
    _exe_name_ = getattr(sys, "_base_executable", sys.executable)
    _exe_args_ = f'"{Path(__file__).resolve()}"'

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
        from app.core.config import SERVICE_DIR
        from app.server import InventoryServer

        servicemanager.LogInfoMsg("Inventario Asserta: iniciando")
        self.server = InventoryServer(log_file=str(SERVICE_DIR / "logs" / "service.log"))

        def run():
            try:
                self.server.run()
            except Exception as exc:  # noqa: BLE001 - se registra y se para el servicio
                import traceback

                servicemanager.LogErrorMsg(f"Inventario Asserta no pudo arrancar: {exc}\n{traceback.format_exc()}")
                win32event.SetEvent(self.stop_event)

        thread = threading.Thread(target=run, daemon=True)
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
