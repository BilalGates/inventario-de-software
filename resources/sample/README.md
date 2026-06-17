# resources/sample — datos de ejemplo anónimos

Esta carpeta contiene **ficheros de ejemplo totalmente anónimos** para probar la
importación sin usar datos reales de inventario.

| Fichero | Para qué sirve | Formato |
|---|---|---|
| `Inventario_Equipos_SAMPLE.csv` | Probar la importación de hardware (`scripts/importar_equipos_csv.py`, página *Inventario Hardware*) | CSV separado por `;`, UTF-8 |
| `panda_export_SAMPLE.txt` | Probar la importación de software de Panda (pegar texto / *Importar Panda*) | Texto separado por tabuladores: `Nombre · Editor · Fecha · Tamaño · Versión` |

## Reglas

- **Nunca** pongas datos reales (nombres de equipo reales, series, MACs, software
  real por departamento) en esta carpeta. Es contenido versionado en git.
- Los datos reales (`resources/*.csv`, `*.xlsx`, `*.vbs`) están **ignorados** por
  `.gitignore` y **no deben subirse al repositorio**. Ver [docs/SEGURIDAD.md](../../docs/SEGURIDAD.md).
- Estos ejemplos son ficticios: cualquier parecido con datos reales es casual.

## Uso rápido

```powershell
# Importar equipos de ejemplo (requiere BD inicializada)
python scripts/importar_equipos_csv.py --file resources/sample/Inventario_Equipos_SAMPLE.csv
```

Para el software, abre la app → *Importar Panda* → pestaña "Pegar texto" y pega el
contenido de `panda_export_SAMPLE.txt`.
