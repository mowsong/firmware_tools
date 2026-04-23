# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

# ── hex_viewer ────────────────────────────────────────────────────────────────
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
    pyz_viewer, a_viewer.scripts, a_viewer.binaries, a_viewer.zipfiles, a_viewer.datas, [],
    name='hex_viewer',
    debug=False, strip=False, upx=True, console=False, upx_exclude=[],
    runtime_tmpdir=None,
    icon='icons/hex_viewer.ico',
)

# ── hex_diff_tool ─────────────────────────────────────────────────────────────
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
    pyz_diff, a_diff.scripts, a_diff.binaries, a_diff.zipfiles, a_diff.datas, [],
    name='hex_diff_tool',
    debug=False, strip=False, upx=True, console=False, upx_exclude=[],
    runtime_tmpdir=None,
    icon='icons/hex_diff_tool.ico',
)