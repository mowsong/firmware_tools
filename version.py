# App registry used by bump_version.py:
#   CLI app name -> variable name in this file
APP_KEYS = {
    "viewer": "__version_viewer__",
    "diff_tool": "__version_diff__",
    "merge": "__version_merge__",
    "serial": "__version_serial__",
}

# Optional aliases for CLI convenience
APP_ALIASES = {
    "diff": "diff_tool",
    "merge_tool": "merge",
}

__version_viewer__ = "1.1.3"
__version_diff__   = "1.1.3"
__version_merge__  = "0.2.1"
__version_serial__ = "0.0.3"