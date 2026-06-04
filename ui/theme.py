"""
Sistema de diseño — tema dark profesional inspirado en JetBrains/VS Code.
"""
from __future__ import annotations

from PySide6.QtWidgets import QApplication

COLORS = {
    # Fondos
    "bg_primary":   "#1e1e2e",
    "bg_secondary": "#181825",
    "bg_tertiary":  "#313244",
    "bg_hover":     "#45475a",
    # Texto
    "text_primary":   "#cdd6f4",
    "text_secondary": "#a6adc8",
    "text_muted":     "#6c7086",
    # Acento
    "accent":       "#89b4fa",
    "accent_hover": "#b4d0f7",
    "accent_dark":  "#1e3a5f",
    # Semánticos
    "success": "#a6e3a1",
    "warning": "#f9e2af",
    "danger":  "#f38ba8",
    "info":    "#74c7ec",
    # Bordes
    "border":       "#45475a",
    "border_focus": "#89b4fa",
}


def apply_theme(app: QApplication) -> None:
    app.setStyleSheet(build_qss())


def build_qss() -> str:
    c = COLORS
    return f"""
/* ─── Base ─────────────────────────────────────────────────────── */
QMainWindow, QWidget {{
    background-color: {c['bg_primary']};
    color: {c['text_primary']};
    font-family: 'Segoe UI', 'Inter', sans-serif;
    font-size: 13px;
}}

QDialog {{
    background-color: {c['bg_secondary']};
    color: {c['text_primary']};
    border: 1px solid {c['border']};
}}

/* ─── Sidebar ───────────────────────────────────────────────────── */
#Sidebar {{
    background-color: {c['bg_secondary']};
    border-right: 1px solid {c['border']};
}}

#SidebarTitle {{
    background-color: {c['bg_secondary']};
    color: {c['text_primary']};
    font-size: 14px;
    font-weight: bold;
    padding: 16px 16px 12px 16px;
    border-bottom: 1px solid {c['border']};
}}

#SidebarVersion {{
    color: {c['text_muted']};
    font-size: 10px;
    padding: 0 16px 12px 16px;
}}

QPushButton#navBtn {{
    background: transparent;
    color: {c['text_secondary']};
    border: none;
    border-radius: 6px;
    padding: 9px 12px;
    text-align: left;
    font-size: 13px;
}}
QPushButton#navBtn:hover {{
    background: {c['bg_hover']};
    color: {c['text_primary']};
}}
QPushButton#navBtn[active="true"] {{
    background: {c['accent_dark']};
    color: {c['accent']};
    font-weight: bold;
}}

/* ─── Tabla QTableView ──────────────────────────────────────────── */
QTableView {{
    background-color: {c['bg_secondary']};
    color: {c['text_primary']};
    gridline-color: {c['border']};
    border: 1px solid {c['border']};
    border-radius: 6px;
    selection-background-color: {c['accent_dark']};
    selection-color: {c['accent']};
    alternate-background-color: {c['bg_tertiary']};
    outline: none;
}}
QTableView::item {{
    padding: 5px 8px;
    border: none;
}}
QTableView::item:hover {{
    background-color: {c['bg_hover']};
}}
QTableView::item:selected {{
    background-color: {c['accent_dark']};
    color: {c['accent']};
}}

QHeaderView::section {{
    background-color: {c['bg_tertiary']};
    color: {c['text_secondary']};
    font-weight: bold;
    padding: 6px 8px;
    border: none;
    border-bottom: 1px solid {c['border']};
    border-right: 1px solid {c['border']};
}}
QHeaderView::section:hover {{
    background-color: {c['bg_hover']};
    color: {c['text_primary']};
}}

/* ─── Inputs ────────────────────────────────────────────────────── */
QLineEdit, QTextEdit, QPlainTextEdit {{
    background-color: {c['bg_tertiary']};
    color: {c['text_primary']};
    border: 1px solid {c['border']};
    border-radius: 5px;
    padding: 6px 8px;
    selection-background-color: {c['accent']};
    selection-color: {c['bg_primary']};
}}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
    border-color: {c['border_focus']};
}}
QLineEdit:disabled, QTextEdit:disabled {{
    background-color: {c['bg_secondary']};
    color: {c['text_muted']};
}}
QLineEdit[readOnly="true"] {{
    background-color: {c['bg_secondary']};
    color: {c['text_muted']};
}}

QComboBox {{
    background-color: {c['bg_tertiary']};
    color: {c['text_primary']};
    border: 1px solid {c['border']};
    border-radius: 5px;
    padding: 5px 8px;
    min-width: 100px;
}}
QComboBox:hover {{
    border-color: {c['accent']};
}}
QComboBox:focus {{
    border-color: {c['border_focus']};
}}
QComboBox::drop-down {{
    border: none;
    width: 20px;
}}
QComboBox::down-arrow {{
    width: 10px;
    height: 10px;
}}
QComboBox QAbstractItemView {{
    background-color: {c['bg_tertiary']};
    color: {c['text_primary']};
    border: 1px solid {c['border']};
    selection-background-color: {c['accent_dark']};
    selection-color: {c['accent']};
    outline: none;
}}

QSpinBox, QDoubleSpinBox {{
    background-color: {c['bg_tertiary']};
    color: {c['text_primary']};
    border: 1px solid {c['border']};
    border-radius: 5px;
    padding: 5px 8px;
}}
QSpinBox:focus, QDoubleSpinBox:focus {{
    border-color: {c['border_focus']};
}}

/* ─── Botones ───────────────────────────────────────────────────── */
QPushButton {{
    background-color: {c['bg_tertiary']};
    color: {c['text_primary']};
    border: 1px solid {c['border']};
    border-radius: 5px;
    padding: 6px 14px;
    font-size: 13px;
}}
QPushButton:hover {{
    background-color: {c['bg_hover']};
    border-color: {c['accent']};
}}
QPushButton:pressed {{
    background-color: {c['accent_dark']};
}}
QPushButton:disabled {{
    background-color: {c['bg_secondary']};
    color: {c['text_muted']};
    border-color: {c['border']};
}}
QPushButton#primary {{
    background-color: {c['accent']};
    color: {c['bg_primary']};
    border: none;
    font-weight: bold;
}}
QPushButton#primary:hover {{
    background-color: {c['accent_hover']};
}}
QPushButton#primary:disabled {{
    background-color: {c['accent_dark']};
    color: {c['text_muted']};
}}
QPushButton#danger {{
    background-color: {c['danger']};
    color: {c['bg_primary']};
    border: none;
    font-weight: bold;
}}
QPushButton#danger:hover {{
    background-color: #f5a0b5;
}}

/* ─── Checkbox / RadioButton ────────────────────────────────────── */
QCheckBox, QRadioButton {{
    color: {c['text_primary']};
    spacing: 6px;
}}
QCheckBox:disabled, QRadioButton:disabled {{
    color: {c['text_muted']};
}}
QCheckBox::indicator {{
    width: 14px;
    height: 14px;
    border: 1px solid {c['border']};
    border-radius: 3px;
    background: {c['bg_tertiary']};
}}
QCheckBox::indicator:checked {{
    background-color: {c['accent']};
    border-color: {c['accent']};
}}

/* ─── Labels ────────────────────────────────────────────────────── */
QLabel {{
    color: {c['text_primary']};
    background: transparent;
}}
QLabel#labelSecondary {{
    color: {c['text_secondary']};
}}
QLabel#labelMuted {{
    color: {c['text_muted']};
    font-size: 11px;
}}
QLabel#labelTitle {{
    font-size: 20px;
    font-weight: bold;
    color: {c['text_primary']};
}}
QLabel#labelSection {{
    font-size: 14px;
    font-weight: bold;
    color: {c['text_secondary']};
    padding-bottom: 4px;
}}
QLabel#badge_success {{
    background-color: {c['success']};
    color: {c['bg_primary']};
    border-radius: 3px;
    padding: 2px 6px;
    font-size: 11px;
    font-weight: bold;
}}
QLabel#badge_danger {{
    background-color: {c['danger']};
    color: {c['bg_primary']};
    border-radius: 3px;
    padding: 2px 6px;
    font-size: 11px;
    font-weight: bold;
}}
QLabel#badge_warning {{
    background-color: {c['warning']};
    color: {c['bg_primary']};
    border-radius: 3px;
    padding: 2px 6px;
    font-size: 11px;
    font-weight: bold;
}}

/* ─── GroupBox ──────────────────────────────────────────────────── */
QGroupBox {{
    color: {c['text_secondary']};
    border: 1px solid {c['border']};
    border-radius: 6px;
    margin-top: 12px;
    padding-top: 10px;
    font-weight: bold;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 6px;
    left: 12px;
    color: {c['text_secondary']};
}}

/* ─── TabWidget ─────────────────────────────────────────────────── */
QTabWidget::pane {{
    background-color: {c['bg_primary']};
    border: 1px solid {c['border']};
    border-top: none;
}}
QTabBar::tab {{
    background-color: {c['bg_secondary']};
    color: {c['text_muted']};
    border: 1px solid {c['border']};
    border-bottom: none;
    border-radius: 4px 4px 0 0;
    padding: 7px 16px;
    margin-right: 2px;
}}
QTabBar::tab:selected {{
    background-color: {c['bg_primary']};
    color: {c['text_primary']};
    font-weight: bold;
}}
QTabBar::tab:hover {{
    background-color: {c['bg_hover']};
    color: {c['text_primary']};
}}

/* ─── ScrollBar ─────────────────────────────────────────────────── */
QScrollBar:vertical {{
    background: {c['bg_secondary']};
    width: 8px;
    border-radius: 4px;
}}
QScrollBar::handle:vertical {{
    background: {c['border']};
    border-radius: 4px;
    min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{
    background: {c['text_muted']};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QScrollBar:horizontal {{
    background: {c['bg_secondary']};
    height: 8px;
    border-radius: 4px;
}}
QScrollBar::handle:horizontal {{
    background: {c['border']};
    border-radius: 4px;
    min-width: 24px;
}}
QScrollBar::handle:horizontal:hover {{
    background: {c['text_muted']};
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
}}

/* ─── StatusBar ─────────────────────────────────────────────────── */
QStatusBar {{
    background-color: {c['bg_secondary']};
    color: {c['text_muted']};
    border-top: 1px solid {c['border']};
    font-size: 11px;
    padding: 2px 8px;
}}

/* ─── Tooltip ───────────────────────────────────────────────────── */
QToolTip {{
    background-color: {c['bg_tertiary']};
    color: {c['text_primary']};
    border: 1px solid {c['border']};
    border-radius: 4px;
    padding: 4px 8px;
}}

/* ─── Splitter ──────────────────────────────────────────────────── */
QSplitter::handle {{
    background-color: {c['border']};
    width: 1px;
    height: 1px;
}}

/* ─── MessageBox ────────────────────────────────────────────────── */
QMessageBox {{
    background-color: {c['bg_secondary']};
    color: {c['text_primary']};
}}
QMessageBox QLabel {{
    color: {c['text_primary']};
}}

/* ─── ProgressBar ───────────────────────────────────────────────── */
QProgressBar {{
    background-color: {c['bg_tertiary']};
    border: 1px solid {c['border']};
    border-radius: 4px;
    text-align: center;
    color: {c['text_primary']};
    font-size: 11px;
}}
QProgressBar::chunk {{
    background-color: {c['accent']};
    border-radius: 3px;
}}

/* ─── Frame separador ───────────────────────────────────────────── */
QFrame[frameShape="4"], QFrame[frameShape="HLine"] {{
    color: {c['border']};
    background-color: {c['border']};
    max-height: 1px;
    border: none;
}}
QFrame[frameShape="5"], QFrame[frameShape="VLine"] {{
    color: {c['border']};
    background-color: {c['border']};
    max-width: 1px;
    border: none;
}}
"""
