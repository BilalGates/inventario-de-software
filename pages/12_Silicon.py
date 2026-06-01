from __future__ import annotations

import streamlit as st

from modules.departamento_page import render_departamento_page
from utils.theme import apply_theme, sidebar_logo


apply_theme()
sidebar_logo()

render_departamento_page("silicon")
