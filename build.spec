# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

block_cipher = None

# Collect all pygame dependencies (DLLs, data files)
pygame_datas, pygame_binaries, pygame_hiddenimports = collect_all('pygame')

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=pygame_binaries,
    datas=[
        ('.env', '.'),
        ('sound', 'sound'),
    ] + pygame_datas,
    hiddenimports=[
        'supabase',
        'postgrest',
        'realtime',
        'storage3',
        'gotrue',
        'httpx',
        'httpcore',
        'pygame',
    ] + pygame_hiddenimports,
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
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='L2M_BossTimer_v2',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
