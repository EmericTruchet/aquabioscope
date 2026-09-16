# -*- mode: python ; coding: utf-8 -*-
# Spec PyInstaller pour Linux (doit être exécuté sur Linux, ex. via GitHub Actions).
# Produit un dossier (onedir) qui sert de base à l'AppImage.

a = Analysis(
    ['run_aquabioscope.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('src/aquabioscope/data/species.csv', 'aquabioscope/data'),
        ('src/aquabioscope/assets/app_icon.ico', 'aquabioscope/assets'),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='AquaBioScope',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
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
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='AquaBioScope',
)
