from __future__ import annotations

import streamlit as st


ASSERTA_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

/* ── Global ─────────────────────────────────────────────────────── */
html, body, [class*="css"], .stApp {
    font-family: 'Inter', sans-serif !important;
}
.stApp {
    background-color: #F4F7FA !important;
}
.main .block-container {
    padding: 2rem 2.5rem 3rem !important;
    max-width: 1400px !important;
}

/* ── Sidebar ─────────────────────────────────────────────────────── */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #2E1A47 0%, #1A237E 100%) !important;
    min-width: 280px !important;
    max-width: 280px !important;
    border-right: none !important;
}
[data-testid="stSidebarContent"] {
    padding: 0 !important;
}
[data-testid="stSidebarNav"] {
    padding: 8px 12px !important;
}
[data-testid="stSidebarNav"] a {
    color: rgba(255,255,255,0.70) !important;
    border-radius: 10px !important;
    padding: 9px 14px !important;
    font-size: 13px !important;
    font-weight: 400 !important;
    margin: 2px 0 !important;
    transition: background 0.15s, color 0.15s !important;
}
[data-testid="stSidebarNav"] a:hover {
    background: rgba(255,255,255,0.10) !important;
    color: #fff !important;
}
[data-testid="stSidebarNav"] a[aria-current="page"] {
    background: rgba(0,176,255,0.18) !important;
    color: #fff !important;
    font-weight: 500 !important;
    border-left: 2px solid #00B0FF !important;
    padding-left: 12px !important;
}
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] span,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] .stSelectbox label,
[data-testid="stSidebar"] .stMultiSelect label {
    color: rgba(255,255,255,0.80) !important;
}
[data-testid="stSidebar"] .stSelectbox > div > div,
[data-testid="stSidebar"] .stMultiSelect > div > div {
    background: rgba(255,255,255,0.10) !important;
    border-color: rgba(255,255,255,0.15) !important;
    color: #fff !important;
}

/* ── Tipografía ──────────────────────────────────────────────────── */
h1 {
    font-size: 22px !important;
    font-weight: 600 !important;
    color: #1E293B !important;
    margin-bottom: 4px !important;
}
h2 {
    font-size: 17px !important;
    font-weight: 600 !important;
    color: #1E293B !important;
}
h3 {
    font-size: 14px !important;
    font-weight: 600 !important;
    color: #374151 !important;
}
p, div, span, label {
    font-size: 14px !important;
    color: #374151 !important;
}

/* ── Métricas nativas (st.metric) ───────────────────────────────── */
[data-testid="stMetric"] {
    background: #FFFFFF !important;
    border-radius: 16px !important;
    border: 1px solid #E2E8F0 !important;
    box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05) !important;
    padding: 20px 20px 16px !important;
}
[data-testid="stMetricLabel"] {
    font-size: 12px !important;
    font-weight: 500 !important;
    color: #94A3B8 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.04em !important;
}
[data-testid="stMetricValue"] {
    font-size: 28px !important;
    font-weight: 600 !important;
    color: #1E293B !important;
}
[data-testid="stMetricDelta"] {
    font-size: 12px !important;
}

/* ── Dataframes / tablas ────────────────────────────────────────── */
[data-testid="stDataFrame"] {
    border-radius: 16px !important;
    overflow: hidden !important;
    border: 1px solid #E2E8F0 !important;
    box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05) !important;
}
[data-testid="stDataFrame"] iframe {
    border-radius: 16px !important;
}

/* ── Botones ─────────────────────────────────────────────────────── */
.stButton > button[kind="primary"],
.stButton > button[data-testid="stBaseButton-primary"] {
    background: linear-gradient(135deg, #2E1A47 0%, #1A237E 100%) !important;
    color: #ffffff !important;
    border: none !important;
    border-radius: 10px !important;
    font-weight: 500 !important;
    font-size: 13px !important;
    padding: 8px 20px !important;
    transition: opacity 0.15s !important;
}
.stButton > button[kind="primary"]:hover {
    opacity: 0.88 !important;
}
.stButton > button {
    border-radius: 10px !important;
    font-weight: 500 !important;
    font-size: 13px !important;
    border-color: #E2E8F0 !important;
}
.stButton > button:hover {
    background: #F8FAFC !important;
    border-color: #CBD5E1 !important;
}

/* ── Inputs de texto y selectbox ────────────────────────────────── */
.stTextInput > div > div > input,
.stTextArea > div > div > textarea {
    border-radius: 10px !important;
    border: 1px solid #E2E8F0 !important;
    background: #fff !important;
    font-size: 13px !important;
    color: #374151 !important;
    transition: border-color 0.15s !important;
}
.stTextInput > div > div > input:focus,
.stTextArea > div > div > textarea:focus {
    border-color: #00B0FF !important;
    box-shadow: 0 0 0 3px rgba(0,176,255,0.12) !important;
}
.stSelectbox > div > div,
.stMultiSelect > div > div {
    border-radius: 10px !important;
    border: 1px solid #E2E8F0 !important;
    background: #fff !important;
    font-size: 13px !important;
}

/* ── Tabs ────────────────────────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] {
    gap: 4px !important;
    background: transparent !important;
    border-bottom: 1px solid #E2E8F0 !important;
    padding-bottom: 0 !important;
}
.stTabs [data-baseweb="tab"] {
    border-radius: 8px 8px 0 0 !important;
    font-size: 13px !important;
    font-weight: 500 !important;
    color: #64748B !important;
    padding: 8px 16px !important;
    background: transparent !important;
    border-bottom: 2px solid transparent !important;
}
.stTabs [aria-selected="true"] {
    color: #2E1A47 !important;
    border-bottom: 2px solid #2E1A47 !important;
    background: transparent !important;
}

/* ── Expanders ───────────────────────────────────────────────────── */
.streamlit-expanderHeader {
    background: #fff !important;
    border-radius: 10px !important;
    border: 1px solid #E2E8F0 !important;
    font-weight: 500 !important;
    font-size: 13px !important;
    color: #374151 !important;
}
[data-testid="stExpander"] {
    border: none !important;
    background: transparent !important;
}

/* ── Forms ───────────────────────────────────────────────────────── */
[data-testid="stForm"] {
    background: #fff !important;
    border-radius: 16px !important;
    border: 1px solid #E2E8F0 !important;
    padding: 20px !important;
    box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05) !important;
}

/* ── Alertas / banners ───────────────────────────────────────────── */
[data-testid="stAlert"] {
    border-radius: 12px !important;
    border-left-width: 4px !important;
    font-size: 13px !important;
}

/* ── Divisores ───────────────────────────────────────────────────── */
hr {
    border-color: #E2E8F0 !important;
    margin: 1.5rem 0 !important;
}

/* ── Download button ─────────────────────────────────────────────── */
[data-testid="stDownloadButton"] > button {
    background: #fff !important;
    color: #2E1A47 !important;
    border: 1px solid #E2E8F0 !important;
    border-radius: 10px !important;
    font-size: 13px !important;
    font-weight: 500 !important;
}
[data-testid="stDownloadButton"] > button:hover {
    background: #F8FAFC !important;
    border-color: #00B0FF !important;
    color: #00B0FF !important;
}

/* ── Scrollbar discreta ──────────────────────────────────────────── */
::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: #CBD5E1; border-radius: 99px; }

/* ── Ocultar chrome nativo de Streamlit (sin usuarios) ───────────── */
/* Header superior con botón Deploy, menú ⋮ y gestión de usuarios    */
header[data-testid="stHeader"] { display: none !important; }
[data-testid="stToolbar"] { display: none !important; }
[data-testid="stDecoration"] { display: none !important; }
[data-testid="stStatusWidget"] { display: none !important; }
#MainMenu { display: none !important; }
/* Footer "Made with Streamlit" */
footer { display: none !important; }
/* Compensar el padding superior que Streamlit añade para el header */
.main .block-container {
    padding-top: 2rem !important;
}
</style>
"""


def apply_theme() -> None:
    st.markdown(ASSERTA_CSS, unsafe_allow_html=True)


def sidebar_logo() -> None:
    st.sidebar.markdown(
        """
        <div style="padding:28px 20px 16px; border-bottom:1px solid rgba(255,255,255,0.10); margin-bottom:8px;">
          <img
            src="https://asserta.net/wp-content/themes/asserta/img/logo.png"
            style="filter: brightness(0) invert(1); width: 140px; display: block;"
            alt="Asserta"
            onerror="this.style.display='none'; document.getElementById('asserta-logo-fallback').style.display='flex';"
          />
          <div id="asserta-logo-fallback"
            style="display:none; align-items:center; gap:10px;">
            <div style="width:28px;height:28px;background:#00B0FF;border-radius:7px;
                        display:flex;align-items:center;justify-content:center;
                        font-size:14px;font-weight:700;color:#fff;">A</div>
            <span style="font-size:15px;font-weight:600;color:#fff;letter-spacing:0.04em;">ASSERTA</span>
          </div>
          <div style="margin-top:10px;font-size:11px;color:rgba(255,255,255,0.40);
                      letter-spacing:0.03em;">Inventario de Software</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
