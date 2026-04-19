# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['hex_viewer.py'],
    pathex=['e:\\xboot\\mhwisp\\wx_test'],
    binaries=[],
    datas=[
        ('hex_viewer.ico', '.'),  # runtime icon file for os.path.dirname(__file__)
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Common unused stacks to keep output smaller
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
    a.binaries,
    a.datas,
    [],
    name='hex_viewer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # GUI app
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='hex_viewer.ico',
)