"""
Configuracion: conexion a BD y preferencias de interfaz.
"""
from __future__ import annotations

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

from config import APP_NAME, APP_VERSION, DB_CONFIG
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

        layout.addWidget(PageHeader("Configuracion", "Preferencias visuales y conexion local de la aplicacion."))

        self._feedback = FeedbackBar()
        layout.addWidget(self._feedback)

        pref_group = QGroupBox("Preferencias")
        pref_form = QFormLayout(pref_group)
        pref_form.setSpacing(10)

        self._theme_combo = QComboBox()
        self._theme_combo.addItem("Claro sobrio", "light")
        self._theme_combo.addItem("Oscuro limpio", "dark")
        current_mode = get_theme_mode()
        for i in range(self._theme_combo.count()):
            if self._theme_combo.itemData(i) == current_mode:
                self._theme_combo.setCurrentIndex(i)
                break
        self._theme_combo.currentIndexChanged.connect(self._change_theme)
        pref_form.addRow("Tema:", self._theme_combo)

        layout.addWidget(pref_group)

        db_group = QGroupBox("Conexion a base de datos")
        db_form = QFormLayout(db_group)
        db_form.setSpacing(10)

        self._host = QLineEdit(str(DB_CONFIG.get("host", "localhost")))
        db_form.addRow("Host:", self._host)

        self._port = QLineEdit(str(DB_CONFIG.get("port", "3306")))
        db_form.addRow("Puerto:", self._port)

        self._dbname = QLineEdit(str(DB_CONFIG.get("database", "inventario_software")))
        db_form.addRow("Base de datos:", self._dbname)

        self._user = QLineEdit(str(DB_CONFIG.get("user", "root")))
        db_form.addRow("Usuario:", self._user)

        self._password = QLineEdit(str(DB_CONFIG.get("password", "")))
        self._password.setEchoMode(QLineEdit.EchoMode.Password)
        db_form.addRow("Contrasena:", self._password)

        btn_row = QHBoxLayout()
        self._test_btn = QPushButton("Probar conexion")
        self._test_btn.clicked.connect(self._test_connection)
        btn_row.addWidget(self._test_btn)

        self._save_btn = QPushButton("Guardar .env")
        self._save_btn.setObjectName("primary")
        self._save_btn.clicked.connect(self._save_env)
        btn_row.addWidget(self._save_btn)
        btn_row.addStretch()
        db_form.addRow(btn_row)

        layout.addWidget(db_group)

        info_group = QGroupBox("Informacion de la aplicacion")
        info_form = QFormLayout(info_group)
        info_form.addRow("Nombre:", QLabel(APP_NAME))
        info_form.addRow("Version:", QLabel(APP_VERSION))

        import sys
        info_form.addRow("Ejecutable:", QLabel(sys.executable))

        from config import BASE_DIR
        info_form.addRow("Directorio:", QLabel(str(BASE_DIR)))

        layout.addWidget(info_group)
        layout.addStretch()

    def _change_theme(self) -> None:
        app = QApplication.instance()
        if app is None:
            return
        mode = self._theme_combo.currentData()
        set_theme_mode(app, mode)
        self._feedback.show_message("Tema actualizado.", "success")
        self.main_window.set_status("Tema actualizado")

    def _test_connection(self) -> None:
        self._feedback.show_message("Probando conexion...", "info")
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
            self._feedback.show_message("Conexion exitosa.", "success")
            self.main_window.set_status("Conexion verificada")
        except Exception as exc:
            self._feedback.show_message(f"Error de conexion: {exc}", "error")
        finally:
            self._test_btn.setEnabled(True)

    def _save_env(self) -> None:
        from config import BASE_DIR
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
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"No se pudo guardar .env:\n{exc}")
        finally:
            self._save_btn.setEnabled(True)
