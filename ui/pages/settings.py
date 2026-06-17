"""
Configuración: apariencia, conexión a la base de datos e información de la app.
"""
from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from config import APP_NAME, APP_VERSION, BASE_DIR, DB_CONFIG
from ui.components.ui_kit import FeedbackBar, PageHeader
from ui.theme import get_theme_mode, set_theme_mode

if TYPE_CHECKING:
    from ui.main_window import MainWindow


class SettingsPage(QWidget):
    def __init__(self, main_window: "MainWindow") -> None:
        super().__init__()
        self.main_window = main_window
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        layout.addWidget(PageHeader("Configuración", "Apariencia, conexión local y datos de la aplicación."))

        self._feedback = FeedbackBar()
        layout.addWidget(self._feedback)

        layout.addWidget(self._build_appearance_group())
        layout.addWidget(self._build_database_group())
        layout.addWidget(self._build_about_group())
        layout.addStretch()

    # ── Apariencia ─────────────────────────────────────────────────
    def _build_appearance_group(self) -> QGroupBox:
        group = QGroupBox("Apariencia")
        form = QFormLayout(group)
        form.setSpacing(10)
        self._theme_combo = QComboBox()
        self._theme_combo.addItem("Claro", "light")
        self._theme_combo.addItem("Oscuro", "dark")
        current_mode = get_theme_mode()
        for i in range(self._theme_combo.count()):
            if self._theme_combo.itemData(i) == current_mode:
                self._theme_combo.setCurrentIndex(i)
                break
        self._theme_combo.currentIndexChanged.connect(self._change_theme)
        form.addRow("Tema:", self._theme_combo)
        return group

    # ── Base de datos ──────────────────────────────────────────────
    def _build_database_group(self) -> QGroupBox:
        group = QGroupBox("Conexión a base de datos")
        form = QFormLayout(group)
        form.setSpacing(10)

        self._host = QLineEdit(str(DB_CONFIG.get("host", "localhost")))
        form.addRow("Host:", self._host)
        self._port = QLineEdit(str(DB_CONFIG.get("port", "3306")))
        form.addRow("Puerto:", self._port)
        self._dbname = QLineEdit(str(DB_CONFIG.get("database", "inventario_software")))
        form.addRow("Base de datos:", self._dbname)
        self._user = QLineEdit(str(DB_CONFIG.get("user", "root")))
        form.addRow("Usuario:", self._user)
        self._password = QLineEdit(str(DB_CONFIG.get("password", "")))
        self._password.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Contraseña:", self._password)

        btn_row = QHBoxLayout()
        self._test_btn = QPushButton("Probar conexión")
        self._test_btn.clicked.connect(self._test_connection)
        btn_row.addWidget(self._test_btn)
        self._save_btn = QPushButton("Guardar .env")
        self._save_btn.setObjectName("primary")
        self._save_btn.clicked.connect(self._save_env)
        btn_row.addWidget(self._save_btn)
        btn_row.addStretch()
        form.addRow(btn_row)

        hint = QLabel("Los cambios en la conexión se aplican al reiniciar la aplicación.")
        hint.setObjectName("labelMuted")
        form.addRow(hint)
        return group

    # ── Acerca de ──────────────────────────────────────────────────
    def _build_about_group(self) -> QGroupBox:
        group = QGroupBox("Acerca de")
        form = QFormLayout(group)
        form.addRow("Nombre:", QLabel(APP_NAME))
        form.addRow("Versión:", QLabel(APP_VERSION))
        form.addRow("Ejecutable:", QLabel(sys.executable))
        form.addRow("Directorio:", QLabel(str(BASE_DIR)))
        return group

    # ── Acciones ───────────────────────────────────────────────────
    def _change_theme(self) -> None:
        app = QApplication.instance()
        if app is None:
            return
        mode = self._theme_combo.currentData()
        set_theme_mode(app, mode)
        self._feedback.show_message("Tema actualizado. Algunas vistas se ajustan al recargarse.", "success")
        self.main_window.set_status("Tema actualizado")

    def _test_connection(self) -> None:
        self._feedback.show_message("Probando conexión...", "info")
        self._test_btn.setEnabled(False)
        try:
            import pymysql
            conn = pymysql.connect(
                host=self._host.text().strip(),
                port=int(self._port.text().strip() or "3306"),
                user=self._user.text().strip(),
                password=self._password.text(),
                database=self._dbname.text().strip(),
                charset="utf8mb4",
                connect_timeout=5,
            )
            conn.close()
            self._feedback.show_message("Conexión correcta.", "success")
            self.main_window.set_status("Conexión verificada")
        except Exception as exc:  # noqa: BLE001
            self._feedback.show_message(f"Error de conexión: {exc}", "error")
        finally:
            self._test_btn.setEnabled(True)

    def _save_env(self) -> None:
        env_path = BASE_DIR / ".env"
        lines = [
            f"DB_HOST={self._host.text().strip()}",
            f"DB_PORT={self._port.text().strip()}",
            f"DB_NAME={self._dbname.text().strip()}",
            f"DB_USER={self._user.text().strip()}",
            f"DB_PASSWORD={self._password.text()}",
        ]
        self._save_btn.setEnabled(False)
        try:
            env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            self._feedback.show_message(f"Credenciales guardadas en {env_path}.", "success")
            self.main_window.set_status("Credenciales guardadas")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Error", f"No se pudo guardar .env:\n{exc}")
        finally:
            self._save_btn.setEnabled(True)
