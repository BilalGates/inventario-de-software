from __future__ import annotations

from nicegui import ui

import nicegui_app.pages.autorizado  # noqa: F401
import nicegui_app.pages.calidad  # noqa: F401
import nicegui_app.pages.dashboard  # noqa: F401
import nicegui_app.pages.departamento  # noqa: F401
import nicegui_app.pages.empresa  # noqa: F401
import nicegui_app.pages.equipos  # noqa: F401
import nicegui_app.pages.importaciones  # noqa: F401

if __name__ == "__main__":
    ui.run(
        title="Inventario Software - Asserta",
        host="0.0.0.0",
        port=8080,
        dark=False,
        reload=False,
        favicon="A",
        show=True,
    )
