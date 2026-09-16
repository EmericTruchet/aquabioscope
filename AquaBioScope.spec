# -*- mode: python ; coding: utf-8 -*-


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
    a.binaries,
    a.datas,
    [],
    exclude_binaries=False,
    name='AquaBioScope',
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
    icon=['src/aquabioscope/assets/app_icon.ico'],
)
