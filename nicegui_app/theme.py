from __future__ import annotations

from nicegui import ui

BRAND_PRIMARY = "#2E1A47"
BRAND_SECONDARY = "#1A237E"
BRAND_ACCENT = "#00B0FF"
BG_APP = "#F4F7FA"

_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap');

body, .q-page { font-family: 'Inter', sans-serif !important; background: #F4F7FA !important; }

.q-table { border-radius: 14px !important; overflow: hidden; border: 1px solid #E8EDF2 !important; box-shadow: 0 1px 3px rgba(0,0,0,.04) !important; }
.q-table thead tr th { background: #F8FAFC !important; font-size: 10.5px !important; font-weight: 600 !important; color: #94A3B8 !important; letter-spacing: .07em !important; text-transform: uppercase !important; padding: 10px 14px !important; }
.q-table tbody tr td { font-size: 13px !important; color: #374151 !important; padding: 9px 14px !important; }
.q-table tbody tr:hover td { background: #F8FAFC !important; }

.q-card { border-radius: 14px !important; box-shadow: 0 1px 3px rgba(0,0,0,.04) !important; border: 1px solid #E8EDF2 !important; }
.q-field--outlined .q-field__control { border-radius: 10px !important; }
.q-field--focused .q-field__control { border-color: #00B0FF !important; }
.q-field__label { font-size: 13px !important; }
.q-field__native { font-size: 13px !important; font-family: 'Inter', sans-serif !important; }
.q-btn { font-family: 'Inter', sans-serif !important; font-weight: 500 !important; font-size: 13px !important; border-radius: 10px !important; text-transform: none !important; letter-spacing: 0 !important; }
.q-chip { font-size: 11px !important; font-weight: 500 !important; border-radius: 99px !important; }
.q-tab { font-size: 13px !important; font-weight: 500 !important; text-transform: none !important; }
.q-tab--active { color: #2E1A47 !important; }
.q-tabs__content .q-tab__indicator { background: #2E1A47 !important; height: 2px !important; }
.q-dialog .q-card { border-radius: 16px !important; min-width: 420px; }
.q-expansion-item .q-item { border-radius: 10px !important; }
.q-notification { border-radius: 10px !important; font-size: 13px !important; font-family: 'Inter', sans-serif !important; }
.q-header { box-shadow: none !important; border-bottom: 1px solid #E8EDF2 !important; }
.q-drawer { box-shadow: none !important; }
"""


def apply_theme() -> None:
    ui.add_head_html(f"<style>{_CSS}</style>")
