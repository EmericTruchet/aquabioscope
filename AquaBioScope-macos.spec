# -*- mode: python ; coding: utf-8 -*-
# Spec PyInstaller pour macOS (doit être exécuté sur un Mac, ex. via GitHub Actions).
# Équivalent de AquaBioScope.spec (Windows) mais produit une app bundle .app avec icône .icns.

from aquabioscope import __version__

a = Analysis(
    ['run_aquabioscope.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('src/aquabioscope/data/species.csv', 'aquabioscope/data'),
        ('src/aquabioscope/assets/app_icon.icns', 'aquabioscope/assets'),
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
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='AquaBioScope',
)

app = BUNDLE(
    coll,
    name='AquaBioScope.app',
    icon='src/aquabioscope/assets/app_icon.icns',
    bundle_identifier='com.aquabioscope.app',
    info_plist={
        'CFBundleName': 'AquaBioScope',
        'CFBundleDisplayName': 'AquaBioScope',
        'CFBundleShortVersionString': __version__,
        'NSHighResolutionCapable': True,
        'NSHumanReadableCopyright': 'AquaBioScope',
    },
)
