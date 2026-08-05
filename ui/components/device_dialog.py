from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from ui.tokens import SPACING


class DeviceEditDialog(QDialog):
    def __init__(
        self,
        parent: QWidget,
        departamentos: list[dict],
        device: dict | None = None,
    ) -> None:
        super().__init__(parent)
        self._device = device or {}
        self.setWindowTitle("Editar dispositivo" if device else "Nuevo dispositivo")
        self.setModal(True)
        self.setMinimumWidth(560)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACING["xl"], SPACING["lg"], SPACING["xl"], SPACING["lg"])
        layout.setSpacing(SPACING["md"])

        title = QLabel("Datos del dispositivo")
        title.setObjectName("labelSection")
        layout.addWidget(title)

        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setHorizontalSpacing(SPACING["lg"])
        form.setVerticalSpacing(SPACING["sm"])

        self._departamento = QComboBox()
        for dept in departamentos:
            self._departamento.addItem(dept["nombre"], dept["id"])
        selected_dept = self._device.get("departamento_id")
        for index in range(self._departamento.count()):
            if self._departamento.itemData(index) == selected_dept:
                self._departamento.setCurrentIndex(index)
                break

        self._nombre = self._line("nombre")
        self._usuario = QLineEdit(str(self._device.get("notas") or self._device.get("usuario") or ""))
        self._activo = QCheckBox("Activo")
        self._activo.setChecked(bool(self._device.get("activo", True)))
        self._servidor = QCheckBox("Servidor")
        self._servidor.setChecked(bool(self._device.get("es_servidor", False)))

        self._tipo = self._line("tipo_dispositivo")
        self._marca = self._line("marca_modelo")
        self._serie = self._line("num_serie")
        self._mac = self._line("mac_address")
        self._so = self._line("sistema_operativo")
        self._procesador = self._line("procesador")
        self._ram = self._line("ram")
        self._almacenamiento = self._line("almacenamiento")
        self._responsable = self._line("responsable")
        self._ubicacion = self._line("ubicacion")

        form.addRow("Departamento", self._departamento)
        form.addRow("Equipo", self._nombre)
        form.addRow("Usuario", self._usuario)
        form.addRow("Estado", self._activo)
        form.addRow("Servidor", self._servidor)
        form.addRow("Tipo", self._tipo)
        form.addRow("Marca / modelo", self._marca)
        form.addRow("Serie", self._serie)
        form.addRow("MAC", self._mac)
        form.addRow("Sistema operativo", self._so)
        form.addRow("Procesador", self._procesador)
        form.addRow("RAM", self._ram)
        form.addRow("Almacenamiento", self._almacenamiento)
        form.addRow("Responsable", self._responsable)
        form.addRow("Ubicacion", self._ubicacion)
        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        save_btn = buttons.button(QDialogButtonBox.StandardButton.Save)
        cancel_btn = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        save_btn.setText("Guardar")
        save_btn.setObjectName("primary")
        cancel_btn.setText("Cancelar")
        buttons.accepted.connect(self._accept_if_valid)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _line(self, key: str) -> QLineEdit:
        return QLineEdit(str(self._device.get(key) or ""))

    def _accept_if_valid(self) -> None:
        if not self._nombre.text().strip():
            QMessageBox.warning(self, "Dato obligatorio", "El nombre del equipo es obligatorio.")
            return
        self.accept()

    def values(self) -> dict:
        return {
            "departamento_id": self._departamento.currentData(),
            "nombre": self._nombre.text().strip(),
            "notas": self._usuario.text().strip() or None,
            "activo": self._activo.isChecked(),
            "es_servidor": self._servidor.isChecked(),
            "tipo_dispositivo": self._tipo.text().strip() or None,
            "marca_modelo": self._marca.text().strip() or None,
            "num_serie": self._serie.text().strip() or None,
            "mac_address": self._mac.text().strip() or None,
            "sistema_operativo": self._so.text().strip() or None,
            "procesador": self._procesador.text().strip() or None,
            "ram": self._ram.text().strip() or None,
            "almacenamiento": self._almacenamiento.text().strip() or None,
            "responsable": self._responsable.text().strip() or None,
            "ubicacion": self._ubicacion.text().strip() or None,
        }
