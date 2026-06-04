"""
Worker/QThread para ejecutar operaciones de BD sin bloquear la UI.

Uso:
    self._thread = QThread()
    self._worker = Worker(fetch_fn, arg1, arg2)
    self._worker.moveToThread(self._thread)
    self._thread.started.connect(self._worker.run)
    self._worker.finished.connect(self._on_data_loaded)
    self._worker.error.connect(self._on_error)
    self._worker.finished.connect(self._thread.quit)
    self._worker.finished.connect(self._worker.deleteLater)
    self._thread.finished.connect(self._thread.deleteLater)
    self._thread.start()
"""
from __future__ import annotations

from PySide6.QtCore import QObject, QThread, Signal


class Worker(QObject):
    finished = Signal(object)
    error = Signal(str)

    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs

    def run(self) -> None:
        try:
            result = self.fn(*self.args, **self.kwargs)
            self.finished.emit(result)
        except Exception as exc:
            self.error.emit(str(exc))


def run_in_thread(parent, fn, *args, on_done=None, on_error=None, **kwargs) -> QThread:
    """
    Ejecuta fn(*args, **kwargs) en un QThread.
    on_done(result) y on_error(msg) son callbacks opcionales.
    Devuelve el QThread (útil para guardar referencia).
    """
    thread = QThread(parent)
    worker = Worker(fn, *args, **kwargs)
    worker.moveToThread(thread)
    thread.started.connect(worker.run)
    if on_done:
        worker.finished.connect(on_done)
    if on_error:
        worker.error.connect(on_error)
    worker.finished.connect(thread.quit)
    worker.finished.connect(worker.deleteLater)
    thread.finished.connect(thread.deleteLater)
    thread.start()
    return thread
