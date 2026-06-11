"""
Sistema de diseno minimalista con tema claro/oscuro persistente.
"""
from __future__ import annotations

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

THEME_SETTING_KEY = "ui/theme_mode"
VALID_THEME_MODES = {"light", "dark"}

PALETTES = {
    "light": {
        "bg_primary": "#f6f7f9",
        "bg_secondary": "#ffffff",
        "bg_tertiary": "#eef1f5",
        "bg_hover": "#e7ebf0",
        "text_primary": "#17202a",
        "text_secondary": "#4a5565",
        "text_muted": "#7b8794",
        "accent": "#2563eb",
        "accent_hover": "#1d4ed8",
        "accent_dark": "#dbeafe",
        "success": "#16803c",
        "success_bg": "#dcfce7",
        "warning": "#b45309",
        "warning_bg": "#fef3c7",
        "danger": "#dc2626",
        "danger_bg": "#fee2e2",
        "info": "#0369a1",
        "info_bg": "#e0f2fe",
        "border": "#d8dee8",
        "border_focus": "#2563eb",
        "shadow": "#e7ebf0",
    },
    "dark": {
        "bg_primary": "#111827",
        "bg_secondary": "#172033",
        "bg_tertiary": "#202b40",
        "bg_hover": "#2b3852",
        "text_primary": "#e5e7eb",
        "text_secondary": "#cbd5e1",
        "text_muted": "#94a3b8",
        "accent": "#60a5fa",
        "accent_hover": "#93c5fd",
        "accent_dark": "#1e3a5f",
        "success": "#86efac",
        "success_bg": "#123322",
        "warning": "#facc15",
        "warning_bg": "#3b2f11",
        "danger": "#f87171",
        "danger_bg": "#3a171b",
        "info": "#7dd3fc",
        "info_bg": "#0b2b3b",
        "border": "#334155",
        "border_focus": "#60a5fa",
        "shadow": "#0f172a",
    },
}

CURRENT_MODE = "light"
COLORS = PALETTES[CURRENT_MODE]


def get_theme_mode() -> str:
    settings = QSettings("Asserta", "InventarioAsserta")
    mode = settings.value(THEME_SETTING_KEY, "light")
    return mode if mode in VALID_THEME_MODES else "light"


def apply_theme(app: QApplication, mode: str | None = None) -> None:
    resolved = mode if mode in VALID_THEME_MODES else get_theme_mode()
    global CURRENT_MODE, COLORS
    CURRENT_MODE = resolved
    COLORS = PALETTES[resolved]
    app.setProperty("themeMode", resolved)
    app.setStyleSheet(build_qss(resolved))


def set_theme_mode(app: QApplication, mode: str) -> None:
    if mode not in VALID_THEME_MODES:
        mode = "light"
    QSettings("Asserta", "InventarioAsserta").setValue(THEME_SETTING_KEY, mode)
    apply_theme(app, mode)


def build_qss(mode: str = "light") -> str:
    c = PALETTES.get(mode, PALETTES["light"])
    return f"""
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

#Sidebar {{
    background-color: {c['bg_secondary']};
    border-right: 1px solid {c['border']};
}}

#SidebarTitle {{
    color: {c['text_primary']};
    font-size: 14px;
    font-weight: 700;
    padding: 0;
}}

#SidebarVersion {{
    color: {c['text_muted']};
    font-size: 10px;
    padding: 0;
}}

#SidebarGroup {{
    color: {c['text_muted']};
    font-size: 10px;
    font-weight: 700;
    padding: 14px 10px 4px 10px;
    text-transform: uppercase;
}}

QPushButton#navBtn {{
    background: transparent;
    color: {c['text_secondary']};
    border: none;
    border-radius: 6px;
    padding: 9px 10px;
    text-align: left;
}}

QPushButton#navBtn:hover {{
    background: {c['bg_hover']};
    color: {c['text_primary']};
}}

QPushButton#navBtn[active="true"] {{
    background: {c['accent_dark']};
    color: {c['accent']};
    font-weight: 700;
}}

#PageHeaderTitle {{
    color: {c['text_primary']};
    font-size: 22px;
    font-weight: 700;
}}

#PageHeaderSubtitle {{
    color: {c['text_muted']};
    font-size: 12px;
}}

#Toolbar, #FeedbackBar, #EmptyState {{
    background-color: {c['bg_secondary']};
    border: 1px solid {c['border']};
    border-radius: 8px;
}}

QFrame#MetricCard {{
    background-color: {c['bg_secondary']};
    border: 1px solid {c['border']};
    border-radius: 8px;
}}

QLabel#MetricTitle {{
    color: {c['text_muted']};
    font-size: 11px;
    font-weight: 700;
}}

QLabel#MetricValue {{
    color: {c['text_primary']};
    font-size: 25px;
    font-weight: 700;
}}

QLabel#MetricSubtitle {{
    color: {c['text_muted']};
    font-size: 11px;
}}

#FeedbackBar[status="info"] {{
    background-color: {c['info_bg']};
    color: {c['info']};
    border-color: {c['info']};
}}

#FeedbackBar[status="success"] {{
    background-color: {c['success_bg']};
    color: {c['success']};
    border-color: {c['success']};
}}

#FeedbackBar[status="warning"] {{
    background-color: {c['warning_bg']};
    color: {c['warning']};
    border-color: {c['warning']};
}}

#FeedbackBar[status="error"] {{
    background-color: {c['danger_bg']};
    color: {c['danger']};
    border-color: {c['danger']};
}}

#FeedbackText {{
    background: transparent;
    color: inherit;
}}

#EmptyState QLabel {{
    background: transparent;
    color: {c['text_muted']};
}}

QTableView {{
    background-color: {c['bg_secondary']};
    color: {c['text_primary']};
    gridline-color: {c['border']};
    border: 1px solid {c['border']};
    border-radius: 8px;
    selection-background-color: {c['accent_dark']};
    selection-color: {c['accent']};
    alternate-background-color: {c['bg_primary']};
    outline: none;
}}

QTableView::item {{
    padding: 6px 8px;
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
    background-color: {c['bg_secondary']};
    color: {c['text_secondary']};
    font-weight: 700;
    padding: 8px;
    border: none;
    border-bottom: 1px solid {c['border']};
}}

QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
    background-color: {c['bg_secondary']};
    color: {c['text_primary']};
    border: 1px solid {c['border']};
    border-radius: 6px;
    padding: 7px 9px;
    selection-background-color: {c['accent']};
    selection-color: {c['bg_secondary']};
}}

QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus,
QSpinBox:focus, QDoubleSpinBox:focus {{
    border-color: {c['border_focus']};
}}

QLineEdit:disabled, QTextEdit:disabled, QComboBox:disabled {{
    background-color: {c['bg_tertiary']};
    color: {c['text_muted']};
}}

QComboBox::drop-down {{
    border: none;
    width: 24px;
}}

QComboBox QAbstractItemView {{
    background-color: {c['bg_secondary']};
    color: {c['text_primary']};
    border: 1px solid {c['border']};
    selection-background-color: {c['accent_dark']};
    selection-color: {c['accent']};
    outline: none;
}}

QPushButton {{
    background-color: {c['bg_secondary']};
    color: {c['text_primary']};
    border: 1px solid {c['border']};
    border-radius: 6px;
    padding: 7px 13px;
}}

QPushButton:hover {{
    background-color: {c['bg_hover']};
    border-color: {c['text_muted']};
}}

QPushButton:pressed {{
    background-color: {c['bg_tertiary']};
}}

QPushButton:disabled {{
    background-color: {c['bg_tertiary']};
    color: {c['text_muted']};
    border-color: {c['border']};
}}

QPushButton#primary {{
    background-color: {c['accent']};
    color: {c['bg_secondary']};
    border: 1px solid {c['accent']};
    font-weight: 700;
}}

QPushButton#primary:hover {{
    background-color: {c['accent_hover']};
    border-color: {c['accent_hover']};
}}

QPushButton#danger {{
    background-color: {c['danger']};
    color: {c['bg_secondary']};
    border: 1px solid {c['danger']};
    font-weight: 700;
}}

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
    font-weight: 700;
    color: {c['text_primary']};
}}

QLabel#labelSection {{
    font-size: 14px;
    font-weight: 700;
    color: {c['text_secondary']};
    padding-bottom: 2px;
}}

QGroupBox {{
    color: {c['text_secondary']};
    background-color: {c['bg_secondary']};
    border: 1px solid {c['border']};
    border-radius: 8px;
    margin-top: 12px;
    padding: 14px 12px 12px 12px;
    font-weight: 700;
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 6px;
    left: 12px;
}}

QTabWidget::pane {{
    background-color: {c['bg_primary']};
    border: none;
    padding-top: 8px;
}}

QTabBar::tab {{
    background-color: transparent;
    color: {c['text_muted']};
    border: none;
    border-bottom: 2px solid transparent;
    padding: 9px 14px;
    margin-right: 4px;
}}

QTabBar::tab:selected {{
    color: {c['accent']};
    border-bottom-color: {c['accent']};
    font-weight: 700;
}}

QTabBar::tab:hover {{
    color: {c['text_primary']};
}}

QScrollBar:vertical {{
    background: transparent;
    width: 8px;
}}

QScrollBar::handle:vertical {{
    background: {c['border']};
    border-radius: 4px;
    min-height: 24px;
}}

QScrollBar:horizontal {{
    background: transparent;
    height: 8px;
}}

QScrollBar::handle:horizontal {{
    background: {c['border']};
    border-radius: 4px;
    min-width: 24px;
}}

QScrollBar::add-line, QScrollBar::sub-line {{
    width: 0;
    height: 0;
}}

QStatusBar {{
    background-color: {c['bg_secondary']};
    color: {c['text_muted']};
    border-top: 1px solid {c['border']};
    font-size: 11px;
    padding: 2px 8px;
}}

QToolTip {{
    background-color: {c['bg_secondary']};
    color: {c['text_primary']};
    border: 1px solid {c['border']};
    border-radius: 4px;
    padding: 4px 8px;
}}

QProgressBar {{
    background-color: {c['bg_tertiary']};
    border: 1px solid {c['border']};
    border-radius: 5px;
    text-align: center;
    color: {c['text_primary']};
    font-size: 11px;
}}

QProgressBar::chunk {{
    background-color: {c['accent']};
    border-radius: 4px;
}}

QFrame[frameShape="4"], QFrame[frameShape="HLine"] {{
    color: {c['border']};
    background-color: {c['border']};
    max-height: 1px;
    border: none;
}}
"""
