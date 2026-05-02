"""
Usage:
  python bump_version.py all
  python bump_version.py all minor
  python bump_version.py viewer
  python bump_version.py viewer major
  python bump_version.py diff_tool 2.5.1

Apps are defined in version.py via APP_KEYS.
Optional aliases are defined via APP_ALIASES.
"""
import importlib.util
import re
import sys
from pathlib import Path

VERSION_FILE = Path(__file__).with_name("version.py")
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")


def load_version_module():
    spec = importlib.util.spec_from_file_location("version", VERSION_FILE)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {VERSION_FILE}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def bump(current: str, part: str) -> str:
    major, minor, patch = map(int, current.split("."))
    if part == "major":
        return f"{major + 1}.0.0"
    if part == "minor":
        return f"{major}.{minor + 1}.0"
    if part == "patch":
        return f"{major}.{minor}.{patch + 1}"
    raise ValueError(f"Invalid bump value '{part}'. Use patch|minor|major|X.Y.Z")


def replace_version_value(content: str, var_name: str, new_value: str) -> str:
    pattern = rf'^(\s*{re.escape(var_name)}\s*=\s*")([^"]+)(".*)$'
    updated, count = re.subn(pattern, rf'\g<1>{new_value}\g<3>', content, count=1, flags=re.MULTILINE)
    if count != 1:
        raise RuntimeError(f"Could not update '{var_name}' in {VERSION_FILE.name}")
    return updated


def main() -> int:
    mod = load_version_module()

    app_keys = getattr(mod, "APP_KEYS", None)
    app_aliases = getattr(mod, "APP_ALIASES", {})

    if not isinstance(app_keys, dict) or not app_keys:
        print("Error: version.py must define non-empty APP_KEYS dict.", file=sys.stderr)
        return 1
    if not isinstance(app_aliases, dict):
        print("Error: APP_ALIASES in version.py must be a dict.", file=sys.stderr)
        return 1

    args = sys.argv[1:]
    target_raw = args[0] if args else "all"
    part = args[1] if len(args) > 1 else "patch"

    target = app_aliases.get(target_raw, target_raw)

    valid_targets = set(app_keys.keys()) | {"all"}
    if target not in valid_targets:
        print(f"Unknown app '{target_raw}'. Use one of: {', '.join(sorted(valid_targets))}", file=sys.stderr)
        return 1

    content = VERSION_FILE.read_text(encoding="utf-8")

    # Read current versions from loaded module
    versions = {}
    for app, var_name in app_keys.items():
        if not hasattr(mod, var_name):
            print(f"Error: version.py missing variable '{var_name}' for app '{app}'", file=sys.stderr)
            return 1
        versions[app] = str(getattr(mod, var_name))

    def next_value(current: str) -> str:
        if SEMVER_RE.match(part):
            return part
        return bump(current, part)

    targets = list(app_keys.keys()) if target == "all" else [target]
    for app in targets:
        versions[app] = next_value(versions[app])
        content = replace_version_value(content, app_keys[app], versions[app])

    VERSION_FILE.write_text(content, encoding="utf-8")

    print("Updated versions:")
    for app in sorted(app_keys.keys()):
        print(f"  {app}: {versions[app]}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())