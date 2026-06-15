# Especificación — aviso de documento histórico

> ℹ️ **Esta especificación ya no es la fuente vigente.**

El proyecto nació con una especificación basada en **Streamlit**. Desde la
versión **2.0** la arquitectura real es **PySide6 + MySQL** (aplicación de
escritorio nativa), no Streamlit.

La especificación original de Streamlit se conserva, solo como referencia
histórica, en:

- [docs/archive/SPEC_streamlit_original.md](docs/archive/SPEC_streamlit_original.md)

## Documentación vigente

| Tema | Documento |
|---|---|
| Visión general / uso | [README.md](README.md) |
| Arquitectura actual | [docs/ARQUITECTURA.md](docs/ARQUITECTURA.md) |
| Modelo de datos | [docs/MODELO_DATOS.md](docs/MODELO_DATOS.md) |
| Instalación y operación | [docs/OPERACION.md](docs/OPERACION.md) |
| Seguridad y datos sensibles | [docs/SEGURIDAD.md](docs/SEGURIDAD.md) |
| Decisiones de arquitectura (ADR) | [docs/adr/](docs/adr/) |

> No tomes decisiones de implementación a partir del documento archivado:
> describe un stack (Streamlit, carpeta `pages/`, `streamlit run app.py`) que ya
> **no se usa**.
