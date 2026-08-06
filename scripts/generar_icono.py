"""
Genera el icono de la aplicacion (resources/icons/app.ico y app.png).

El diseno usa el azul de acento del tema (#2563eb): un cuadrado redondeado
con una "A" de Asserta formada por tres barras apiladas, que evocan las
filas de un inventario.

Uso:
    python scripts/generar_icono.py
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
ICONS_DIR = ROOT / "resources" / "icons"

# Azul de acento del tema (ui/theme.py -> PALETTES["light"]["accent"]).
ACCENT = (37, 99, 235, 255)
ACCENT_DARK = (29, 78, 216, 255)
WHITE = (255, 255, 255, 255)
WHITE_SOFT = (234, 241, 254, 255)

# Lienzo grande y luego reducimos: da bordes suaves sin antialias manual.
CANVAS = 1024


def _rounded_background(img: Image.Image) -> None:
    """Fondo redondeado con un degradado vertical suave del azul de acento."""
    radius = int(CANVAS * 0.22)

    # Degradado lineal: fila a fila de ACCENT a ACCENT_DARK.
    gradient = Image.new("RGBA", (1, CANVAS))
    for y in range(CANVAS):
        t = y / (CANVAS - 1)
        gradient.putpixel(
            (0, y),
            tuple(round(a + (b - a) * t) for a, b in zip(ACCENT, ACCENT_DARK)),
        )
    gradient = gradient.resize((CANVAS, CANVAS))

    # Mascara con las esquinas redondeadas.
    mask = Image.new("L", (CANVAS, CANVAS), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (0, 0, CANVAS - 1, CANVAS - 1), radius=radius, fill=255
    )
    img.paste(gradient, (0, 0), mask)


def _draw_monogram(draw: ImageDraw.ImageDraw) -> None:
    """Dibuja una 'A' con dos diagonales y un travesano."""
    cx = CANVAS / 2
    top_y = CANVAS * 0.24
    bottom_y = CANVAS * 0.76
    half_base = CANVAS * 0.20
    thickness = int(CANVAS * 0.085)

    # Diagonales de la A.
    draw.line(
        [(cx - half_base, bottom_y), (cx, top_y)],
        fill=WHITE,
        width=thickness,
        joint="curve",
    )
    draw.line(
        [(cx + half_base, bottom_y), (cx, top_y)],
        fill=WHITE,
        width=thickness,
        joint="curve",
    )
    # Remate superior redondeado.
    r = thickness / 2
    draw.ellipse((cx - r, top_y - r, cx + r, top_y + r), fill=WHITE)

    # Travesano de la A: la "fila" del inventario, en azul claro.
    bar_y = CANVAS * 0.605
    bar_half = CANVAS * 0.105
    bar_h = int(CANVAS * 0.062)
    draw.rounded_rectangle(
        (cx - bar_half, bar_y - bar_h / 2, cx + bar_half, bar_y + bar_h / 2),
        radius=bar_h // 2,
        fill=WHITE_SOFT,
    )


def build_icon() -> Image.Image:
    img = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
    _rounded_background(img)
    _draw_monogram(ImageDraw.Draw(img))
    return img


def main() -> int:
    ICONS_DIR.mkdir(parents=True, exist_ok=True)
    img = build_icon()

    png_path = ICONS_DIR / "app.png"
    img.resize((512, 512), Image.LANCZOS).save(png_path, format="PNG")

    # .ico multi-resolucion: Windows elige el tamano segun el contexto
    # (barra de tareas, escritorio, alt-tab).
    ico_path = ICONS_DIR / "app.ico"
    sizes = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]
    img.save(ico_path, format="ICO", sizes=sizes)

    print(f"OK  {png_path.relative_to(ROOT)}")
    print(f"OK  {ico_path.relative_to(ROOT)}  ({len(sizes)} resoluciones)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
