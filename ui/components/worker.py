"""
Worker para ejecutar operaciones de BD sin bloquear la UI.

ESTRATEGIA: threading.Thread (stdlib) + QApplication.postEvent para entregar
callbacks en el hilo principal.

QApplication.postEvent es explícitamente thread-safe en Qt y es el mecanismo
correcto para cruzar desde un hilo secundario (sin event loop Qt) al hilo principal.

Uso:
    self._thread = run_in_thread(
        self,               # parent (QObject/QWidget)
        fetch_fn,           # función que corre en el hilo secundario
        arg1, arg2,         # args posicionales para fetch_fn
        on_done=self._on_data_loaded,
        on_error=self._on_error,
    )
    # Guardar self._thread es obligatorio — mantiene _Receiver vivo.
"""
from __future__ import annotations

import threading
from typing import Callable

from PySide6.QtCore import QEvent, QObject, Slot
from PySide6.QtWidgets import QApplication


# IDs de evento personalizados (únicos por tipo)
_DONE_EVENT_TYPE = QEvent.Type(QEvent.Type.User + 100)
_ERROR_EVENT_TYPE = QEvent.Type(QEvent.Type.User + 101)


class _DoneEvent(QEvent):
    def __init__(self, result):
        super().__init__(_DONE_EVENT_TYPE)
        self.result = result


class _ErrorEvent(QEvent):
    def __init__(self, msg: str):
        super().__init__(_ERROR_EVENT_TYPE)
        self.msg = msg


class _Receiver(QObject):
    """
    QObject en el hilo principal que recibe eventos desde el hilo secundario.
    QApplication.postEvent() es thread-safe y garantiza entrega en el hilo del receptor.
    """

    def __init__(
        self,
        on_done: Callable | None,
        on_error: Callable | None,
        parent: QObject | None = None,
    ):
        super().__init__(parent)
        self._on_done = on_done
        self._on_error = on_error

    def customEvent(self, event: QEvent) -> None:
        if event.type() == _DONE_EVENT_TYPE:
            if self._on_done:
                try:
                    self._on_done(event.result)
                except Exception:
                    import traceback
                    traceback.print_exc()
        elif event.type() == _ERROR_EVENT_TYPE:
            if self._on_error:
                try:
                    self._on_error(event.msg)
                except Exception:
                    import traceback
                    traceback.print_exc()


class _ThreadHandle:
    """Devuelto por run_in_thread — mantiene receiver vivo vía referencia Python."""
    def __init__(self, thread: threading.Thread, receiver: _Receiver):
        self._thread = thread
        self._receiver = receiver

    def is_alive(self) -> bool:
        return self._thread.is_alive()


def run_in_thread(
    parent: QObject | None,
    fn: Callable,
    *args,
    on_done: Callable | None = None,
    on_error: Callable | None = None,
    **kwargs,
) -> _ThreadHandle:
    """
    Ejecuta fn(*args, **kwargs) en un hilo secundario.
    on_done(result) y on_error(msg) se llaman en el hilo principal via postEvent.
    """
    receiver = _Receiver(on_done, on_error, parent)

    def task() -> None:
        try:
            result = fn(*args, **kwargs)
            # postEvent es thread-safe: entrega el evento al hilo de receiver (main)
            QApplication.postEvent(receiver, _DoneEvent(result))
        except Exception as exc:
            QApplication.postEvent(receiver, _ErrorEvent(str(exc)))

    t = threading.Thread(target=task, daemon=True)
    t.start()
    return _ThreadHandle(t, receiver)
