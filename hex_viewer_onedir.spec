# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['hex_viewer.py'],
    pathex=['e:\\xboot\\mhwisp\\wx_test'],
    binaries=[],
    datas=[
        ('hex_viewer.ico', '.'),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'unittest',
        'test',
        'pytest',
        'numpy',
        'pandas',
        'scipy',
        'matplotlib',
        'IPython',
        'jupyter',
        'notebook',
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='hex_viewer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    icon='hex_viewer.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='hex_viewer',
)