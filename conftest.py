"""Configuración global de pytest: garantiza que la raíz del proyecto esté en sys.path."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
