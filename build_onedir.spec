# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

# -- hex_viewer ---------------------------------------------------------------
a_viewer = Analysis(
    ['hex_viewer.py'],
    pathex=[],
    binaries=[],
    datas=[('icons', 'icons')],
    hiddenimports=['intelhex', 'wx', 'wx.stc'],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    cipher=block_cipher,
)

pyz_viewer = PYZ(a_viewer.pure, a_viewer.zipped_data, cipher=block_cipher)

exe_viewer = EXE(
    pyz_viewer,
    a_viewer.scripts,
    [],
    exclude_binaries=True,
    name='hex_viewer',
    debug=False,
    strip=False,
    upx=True,
    console=False,
    icon='icons/hex_viewer.ico',
)

coll_viewer = COLLECT(
    exe_viewer,
    a_viewer.binaries,
    a_viewer.zipfiles,
    a_viewer.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='hex_viewer',
)

# -- hex_diff_tool ------------------------------------------------------------
a_diff = Analysis(
    ['hex_diff_tool.py'],
    pathex=[],
    binaries=[],
    datas=[('icons', 'icons')],
    hiddenimports=['intelhex', 'wx', 'wx.stc'],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    cipher=block_cipher,
)

pyz_diff = PYZ(a_diff.pure, a_diff.zipped_data, cipher=block_cipher)

exe_diff = EXE(
    pyz_diff,
    a_diff.scripts,
    [],
    exclude_binaries=True,
    name='hex_diff_tool',
    debug=False,
    strip=False,
    upx=True,
    console=False,
    icon='icons/hex_diff_tool.ico',
)

coll_diff = COLLECT(
    exe_diff,
    a_diff.binaries,
    a_diff.zipfiles,
    a_diff.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='hex_diff_tool',
)