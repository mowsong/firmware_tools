# -*- mode: python ; coding: utf-8 -*-
import os

block_cipher = None

UPX_EXCLUDE = [
    'api-ms-win-crt-*.dll',
    'api-ms-win-core-*.dll',
    'ucrtbase.dll',
    'vcruntime*.dll',
    'msvcp*.dll',
    'python3*.dll',
]

ALL_APPS = {"hex_viewer", "hex_diff_tool", "merge_tool"}

# Read selected apps from environment variable set by wrapper script.
# Examples:
#   BUILD_APPS=all
#   BUILD_APPS=hex_viewer,merge_tool
_selected_raw = os.environ.get("BUILD_APPS", "all").strip().lower()

if _selected_raw == "all":
    SELECTED_APPS = ALL_APPS
else:
    SELECTED_APPS = {x.strip() for x in _selected_raw.split(",") if x.strip()}
    unknown = SELECTED_APPS - ALL_APPS
    if unknown:
        raise SystemExit(f"Unknown app(s) in BUILD_APPS: {', '.join(sorted(unknown))}")

# hex_viewer
if "hex_viewer" in SELECTED_APPS:
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
        debug=False, strip=False, upx=True, console=False,
        upx_exclude=UPX_EXCLUDE,
        runtime_tmpdir=None,
        icon='icons/hex_viewer.ico',
    )

# hex_diff_tool
if "hex_diff_tool" in SELECTED_APPS:
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
        debug=False, strip=False, upx=True, console=False,
        upx_exclude=UPX_EXCLUDE,
        runtime_tmpdir=None,
        icon='icons/hex_diff_tool.ico',
    )

# merge_tool
if "merge_tool" in SELECTED_APPS:
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
        debug=False, strip=False, upx=True, console=False,
        upx_exclude=UPX_EXCLUDE,
        runtime_tmpdir=None,
        icon='icons/merge_tool.ico',
    )
