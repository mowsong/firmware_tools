# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

# hex_viewer 
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

# hex_diff_tool
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


# merge_tool 
a_merge = Analysis(
    ['merge_tool.py'],
    pathex=[],
    binaries=[],
    datas=[('icons', 'icons')],
    hiddenimports=['intelhex', 'wx', 'wx.stc'],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    cipher=block_cipher,
)

pyz_merge = PYZ(a_merge.pure, a_merge.zipped_data, cipher=block_cipher)

exe_merge = EXE(
    pyz_merge, a_merge.scripts, a_merge.binaries, a_merge.zipfiles, a_merge.datas, [],
    name='merge_tool',
    debug=False, strip=False, upx=True, console=False, upx_exclude=[],
    runtime_tmpdir=None,
    icon='icons/merge_tool.ico',
)
