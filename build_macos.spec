# -*- mode: python ; coding: utf-8 -*-
# Build spec for macOS

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('.env', '.'),
        ('sound', 'sound'),
    ],
    hiddenimports=[
        'supabase',
        'postgrest',
        'realtime',
        'storage3',
        'gotrue',
        'httpx',
        'httpcore',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib',
        'scipy',
        'numpy',
        'PIL',
        'pandas',
    ],
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
    name='L2M_BossTimer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=True,
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
    name='L2M_BossTimer',
)

app = BUNDLE(
    coll,
    name='L2M_BossTimer.app',
    icon=None,
    bundle_identifier='com.l2m.bosstimer',
    info_plist={
        'CFBundleName': 'L2M Boss Timer',
        'CFBundleDisplayName': 'L2M Boss Timer',
        'CFBundleVersion': '2.2.0',
        'CFBundleShortVersionString': '2.2.0',
        'NSHighResolutionCapable': True,
    },
)
