# -*- mode: python ; coding: utf-8 -*-
# Spec PyInstaller pour macOS (doit être exécuté sur un Mac, ex. via GitHub Actions).
# Équivalent de DivePhoto.spec (Windows) mais produit une app bundle .app avec icône .icns.

a = Analysis(
    ['run_divephoto.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('src/divephoto/data/species.csv', 'divephoto/data'),
        ('src/divephoto/assets/app_icon.icns', 'divephoto/assets'),
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
    name='DivePhoto',
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
    name='DivePhoto',
)

app = BUNDLE(
    coll,
    name='DivePhoto.app',
    icon='src/divephoto/assets/app_icon.icns',
    bundle_identifier='com.divephoto.app',
    info_plist={
        'CFBundleName': 'DivePhoto',
        'CFBundleDisplayName': 'DivePhoto',
        'CFBundleShortVersionString': '0.1.0',
        'NSHighResolutionCapable': True,
        'NSHumanReadableCopyright': 'DivePhoto',
    },
)
