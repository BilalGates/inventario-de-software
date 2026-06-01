# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

block_cipher = None
project_root = Path.cwd()

datas = [
    (str(project_root / "database"), "database"),
    (str(project_root / "migrations"), "migrations"),
    (str(project_root / "migration"), "migration"),
    (str(project_root / ".env"), "."),
    (str(project_root / "Inventario_Software_ENS_Por_Departamento.xlsx"), "."),
    (str(project_root / "Inventario Equipos Informaticos Asserta(Equipos Asserta).csv"), "."),
]

a = Analysis(
    [str(project_root / "main.py")],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=[
        "pymysql",
        "openpyxl",
        "dotenv",
        "migration.migrate_excel",
        "scripts.importar_equipos_csv",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[str(project_root / "build" / "runtime_env.py")],
    excludes=["streamlit"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Inventario Software Asserta",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="Inventario Software Asserta",
)
