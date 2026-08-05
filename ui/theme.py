"""
Sistema de tema: construye el QSS global a partir de los tokens de diseño
(`ui/tokens.py`). Mantiene la API pública usada por el resto de la app:
`apply_theme`, `set_theme_mode`, `get_theme_mode`, `build_qss`, y el dict `COLORS`.
"""
from __future__ import annotations

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from ui.tokens import FONT, HEIGHT, PALETTES, RADIUS, SPACING, badge_colors, tone_for_label

THEME_SETTING_KEY = "ui/theme_mode"
VALID_THEME_MODES = {"light", "dark"}

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


# Helpers expuestos para componentes que pintan estados dinámicos (badges).
def current_palette() -> dict[str, str]:
    return COLORS


def status_colors(label_or_tone: str) -> tuple[str, str]:
    """(texto, fondo) para una etiqueta de estado o un tono semántico."""
    tone = label_or_tone if label_or_tone in {
        "success", "warning", "danger", "info", "accent", "neutral",
    } else tone_for_label(label_or_tone)
    return badge_colors(COLORS, tone)


def build_qss(mode: str = "light") -> str:
    c = PALETTES.get(mode, PALETTES["light"])
    s, r, f, h = SPACING, RADIUS, FONT, HEIGHT
    return f"""
/* ====================== Base ====================== */
QMainWindow, QWidget {{
    background-color: {c['bg_primary']};
    color: {c['text_primary']};
    font-family: {f['family']};
    font-size: {f['body']}px;
}}

QWidget#Surface {{
    background-color: {c['bg_secondary']};
}}

QDialog {{
    background-color: {c['bg_secondary']};
    color: {c['text_primary']};
}}

QToolTip {{
    background-color: {c['text_primary']};
    color: {c['bg_secondary']};
    border: none;
    border-radius: {r['sm']}px;
    padding: {s['xs']}px {s['sm']}px;
}}

/* ====================== Busqueda global ====================== */
QFrame#GlobalSearchBar {{
    background-color: {c['bg_secondary']};
    border: none;
    border-bottom: 1px solid {c['border']};
    border-radius: 0;
}}

QLabel#GlobalSearchLabel {{
    color: {c['text_muted']};
    font-size: {f['tiny']}px;
    font-weight: 700;
}}

QLabel#GlobalBrand {{
    color: {c['text_primary']};
    font-size: {f['section']}px;
    font-weight: 700;
    padding-right: {s['md']}px;
}}

QComboBox#GlobalPeriodCombo {{
    min-width: 54px;
    padding-left: {s['sm']}px;
    padding-right: {s['sm']}px;
}}

/* ====================== Cabecera de página ====================== */
#PageHeaderTitle {{
    color: {c['text_primary']};
    font-size: {f['title']}px;
    font-weight: 600;
}}

#PageHeaderSubtitle {{
    color: {c['text_secondary']};
    font-size: {f['subtitle']}px;
}}

/* ====================== Tarjetas / superficies ====================== */
#Toolbar, #FilterBar, #FeedbackBar, #EmptyState, QFrame#SectionCard, #DetailPanel {{
    background-color: {c['bg_secondary']};
    border: 1px solid {c['border']};
    border-radius: {r['md']}px;
}}

QFrame#DetailPanel {{
    background-color: {c['bg_secondary']};
    border: none;
    border-left: 1px solid {c['border']};
    border-radius: 0;
}}

QScrollArea#DetailPanelScroll,
QWidget#DetailPanelViewport,
QWidget#DetailPanelContent,
QWidget#DetailField,
QWidget#InventoryTab {{
    background-color: {c['bg_secondary']};
    border: none;
}}

#SectionTitle {{
    color: {c['text_primary']};
    font-size: {f['section']}px;
    font-weight: 600;
}}

QFrame#DepartmentCard {{
    background-color: {c['bg_secondary']};
    border: 1px solid {c['border']};
    border-radius: {r['md']}px;
}}

QFrame#DepartmentCard:hover {{
    background-color: {c['bg_hover']};
    border-color: {c['border_strong']};
}}

QFrame#DepartmentCard[selected="true"] {{
    background-color: {c['accent_soft']};
    border: 1px solid {c['accent']};
}}

QLabel#DepartmentCardTitle {{
    color: {c['text_primary']};
    font-size: {f['section']}px;
    font-weight: 700;
}}

QLabel#DepartmentCardMetric {{
    color: {c['text_primary']};
    font-size: {f['body']}px;
    font-weight: 600;
}}

QLabel#DepartmentCardMeta {{
    color: {c['text_secondary']};
    font-size: {f['small']}px;
}}

/* ====================== FeedbackBar (estados) ====================== */
#FeedbackBar[status="info"]    {{ background-color: {c['info_soft']};    color: {c['info']};    border-color: {c['info']}; }}
#FeedbackBar[status="success"] {{ background-color: {c['success_soft']}; color: {c['success']}; border-color: {c['success']}; }}
#FeedbackBar[status="warning"] {{ background-color: {c['warning_soft']}; color: {c['warning']}; border-color: {c['warning']}; }}
#FeedbackBar[status="error"]   {{ background-color: {c['danger_soft']};  color: {c['danger']};  border-color: {c['danger']}; }}
#FeedbackText {{ background: transparent; color: inherit; }}

#EmptyState QLabel {{ background: transparent; }}
#EmptyStateIcon {{ color: {c['text_muted']}; font-size: 32px; }}
#EmptyStateTitle {{ color: {c['text_primary']}; font-size: {f['section']}px; font-weight: 600; }}
#EmptyStateBody {{ color: {c['text_secondary']}; font-size: {f['subtitle']}px; }}

/* ====================== Tablas ====================== */
QTableView {{
    background-color: {c['bg_secondary']};
    color: {c['text_primary']};
    gridline-color: transparent;
    border: 1px solid {c['border']};
    border-radius: {r['md']}px;
    selection-background-color: {c['bg_active']};
    selection-color: {c['text_primary']};
    alternate-background-color: {c['bg_primary']};
    outline: none;
}}

QTableView#InventoryTable {{
    border: none;
    border-right: 1px solid {c['border']};
    border-radius: 0;
}}

QTableView::item {{
    padding: {s['sm']}px {s['md']}px;
    border: none;
    border-bottom: 1px solid {c['border']};
}}

QTableView::item:selected {{
    background-color: {c['bg_active']};
    color: {c['text_primary']};
}}

QHeaderView::section {{
    background-color: {c['bg_secondary']};
    color: {c['text_secondary']};
    font-weight: 600;
    font-size: {f['small']}px;
    padding: {s['sm']}px {s['md']}px;
    border: none;
    border-bottom: 1px solid {c['border_strong']};
}}

QHeaderView::section:hover {{ color: {c['text_primary']}; }}
QTableCornerButton::section {{ background-color: {c['bg_secondary']}; border: none; }}

/* ====================== Inputs ====================== */
QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
    background-color: {c['bg_secondary']};
    color: {c['text_primary']};
    border: 1px solid {c['border_strong']};
    border-radius: {r['sm']}px;
    padding: {s['sm']}px {s['md']}px;
    min-height: {h['input'] - 2 * s['sm']}px;
    selection-background-color: {c['accent']};
    selection-color: {c['text_on_accent']};
}}

QTextEdit, QPlainTextEdit {{ min-height: 0; }}

QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus,
QSpinBox:focus, QDoubleSpinBox:focus {{
    border: 1px solid {c['border_focus']};
}}

QLineEdit:disabled, QTextEdit:disabled, QComboBox:disabled {{
    background-color: {c['bg_tertiary']};
    color: {c['text_muted']};
}}

QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox QAbstractItemView {{
    background-color: {c['bg_secondary']};
    color: {c['text_primary']};
    border: 1px solid {c['border']};
    border-radius: {r['sm']}px;
    selection-background-color: {c['accent_soft']};
    selection-color: {c['accent']};
    outline: none;
}}

/* ====================== Botones ====================== */
QPushButton {{
    background-color: {c['bg_secondary']};
    color: {c['text_primary']};
    border: 1px solid {c['border_strong']};
    border-radius: {r['sm']}px;
    padding: 0 {s['lg']}px;
    min-height: {h['button']}px;
    font-size: {f['body']}px;
}}

QPushButton:hover {{ background-color: {c['bg_hover']}; }}
QPushButton:pressed {{ background-color: {c['bg_tertiary']}; }}
QPushButton:focus {{ border: 1px solid {c['border_focus']}; }}
QPushButton:disabled {{ background-color: {c['bg_tertiary']}; color: {c['text_muted']}; border-color: {c['border']}; }}

QPushButton#primary {{
    background-color: {c['accent']};
    color: {c['text_on_accent']};
    border: 1px solid {c['accent']};
    font-weight: 600;
}}
QPushButton#primary:hover {{ background-color: {c['accent_hover']}; border-color: {c['accent_hover']}; }}
QPushButton#primary:focus {{ border: 1px solid {c['text_primary']}; }}

QPushButton#danger {{
    background-color: {c['bg_secondary']};
    color: {c['danger']};
    border: 1px solid {c['danger']};
    font-weight: 600;
}}
QPushButton#danger:hover {{ background-color: {c['danger_soft']}; }}

QPushButton#subtle {{
    background: transparent;
    border: 1px solid transparent;
    color: {c['text_secondary']};
}}
QPushButton#subtle:hover {{ background-color: {c['bg_hover']}; color: {c['text_primary']}; }}

QPushButton#link {{
    background: transparent;
    border: none;
    color: {c['accent']};
    text-align: left;
    padding: 0;
    min-height: 0;
}}
QPushButton#link:hover {{ color: {c['accent_hover']}; }}

/* ====================== Etiquetas ====================== */
QLabel {{ color: {c['text_primary']}; background: transparent; }}
QLabel#labelSecondary {{ color: {c['text_secondary']}; }}
QLabel#labelMuted {{ color: {c['text_muted']}; font-size: {f['small']}px; }}
QLabel#labelSection {{ font-size: {f['section']}px; font-weight: 600; color: {c['text_primary']}; }}

/* ====================== GroupBox ====================== */
QGroupBox {{
    color: {c['text_secondary']};
    background-color: {c['bg_secondary']};
    border: 1px solid {c['border']};
    border-radius: {r['md']}px;
    margin-top: {s['md']}px;
    padding: {s['lg']}px {s['md']}px {s['md']}px {s['md']}px;
    font-weight: 600;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 {s['xs']}px;
    left: {s['md']}px;
    color: {c['text_primary']};
}}

/* ====================== Tabs ====================== */
QTabWidget::pane {{ background-color: {c['bg_secondary']}; border: none; }}
QTabBar {{ background-color: {c['bg_secondary']}; }}
QTabBar::tab {{
    background-color: {c['bg_secondary']};
    color: {c['text_secondary']};
    border: none;
    border-bottom: 2px solid transparent;
    padding: {s['sm']}px {s['md']}px;
    margin-right: {s['xs']}px;
}}
QTabBar::tab:selected {{
    background-color: {c['bg_secondary']};
    color: {c['accent']};
    border-bottom-color: {c['accent']};
    font-weight: 600;
}}
QTabBar::tab:hover {{ background-color: {c['bg_secondary']}; color: {c['text_primary']}; }}

/* ====================== Scrollbars ====================== */
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 0; }}
QScrollBar::handle:vertical {{ background: {c['border_strong']}; border-radius: 5px; min-height: 28px; }}
QScrollBar::handle:vertical:hover {{ background: {c['text_muted']}; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 0; }}
QScrollBar::handle:horizontal {{ background: {c['border_strong']}; border-radius: 5px; min-width: 28px; }}
QScrollBar::handle:horizontal:hover {{ background: {c['text_muted']}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

/* ====================== Status bar ====================== */
QStatusBar {{
    background-color: {c['bg_secondary']};
    color: {c['text_muted']};
    border-top: 1px solid {c['border']};
    font-size: {f['tiny']}px;
}}
QStatusBar::item {{ border: none; }}

/* ====================== Progreso ====================== */
QProgressBar {{
    background-color: {c['bg_tertiary']};
    border: none;
    border-radius: {r['sm']}px;
    text-align: center;
    color: {c['text_secondary']};
    font-size: {f['tiny']}px;
    min-height: 6px;
}}
QProgressBar::chunk {{ background-color: {c['accent']}; border-radius: {r['sm']}px; }}

/* ====================== Líneas ====================== */
QFrame[frameShape="4"], QFrame[frameShape="HLine"] {{
    color: {c['border']};
    background-color: {c['border']};
    max-height: 1px;
    border: none;
}}

/* ====================== Diálogos ====================== */
QMessageBox {{ background-color: {c['bg_secondary']}; }}
QMessageBox QLabel {{ color: {c['text_primary']}; }}
"""
