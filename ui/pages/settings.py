"""
Configuración — conexión a BD y preferencias.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
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
        layout.setSpacing(20)

        title = QLabel("Configuración")
        title.setObjectName("labelTitle")
        layout.addWidget(title)

        # ── Conexión BD ──────────────────────────────────────────────
        db_group = QGroupBox("Conexión a base de datos")
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
        db_form.addRow("Contraseña:", self._password)

        btn_row = QHBoxLayout()
        self._test_btn = QPushButton("Probar conexión")
        self._test_btn.clicked.connect(self._test_connection)
        btn_row.addWidget(self._test_btn)
        self._save_btn = QPushButton("Guardar en .env")
        self._save_btn.setObjectName("primary")
        self._save_btn.clicked.connect(self._save_env)
        btn_row.addWidget(self._save_btn)
        btn_row.addStretch()
        db_form.addRow(btn_row)

        self._conn_status = QLabel("")
        self._conn_status.setObjectName("labelSecondary")
        db_form.addRow(self._conn_status)

        layout.addWidget(db_group)

        # ── Información de la app ────────────────────────────────────
        info_group = QGroupBox("Información de la aplicación")
        info_form = QFormLayout(info_group)

        info_form.addRow("Nombre:", QLabel(APP_NAME))
        info_form.addRow("Versión:", QLabel(APP_VERSION))

        import sys
        info_form.addRow("Ejecutable:", QLabel(sys.executable))

        from config import BASE_DIR
        info_form.addRow("Directorio:", QLabel(str(BASE_DIR)))

        layout.addWidget(info_group)
        layout.addStretch()

    def _test_connection(self) -> None:
        self._conn_status.setText("Probando conexión...")
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
            self._conn_status.setStyleSheet("color: #a6e3a1;")
            self._conn_status.setText("Conexión exitosa.")
        except Exception as exc:
            self._conn_status.setStyleSheet("color: #f38ba8;")
            self._conn_status.setText(f"Error: {exc}")

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
        try:
            env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            QMessageBox.information(self, "Guardado", f"Credenciales guardadas en:\n{env_path}")
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"No se pudo guardar .env:\n{exc}")
