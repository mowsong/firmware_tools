"""
Usage:
  python bump_version.py viewer          -> bumps viewer patch  (1.0.0 -> 1.0.1)
  python bump_version.py viewer minor    -> bumps viewer minor
  python bump_version.py viewer major    -> bumps viewer major
  python bump_version.py viewer 2.5.1    -> sets viewer exact version

  python bump_version.py diff            -> bumps diff patch
  python bump_version.py diff minor
  python bump_version.py diff major
  python bump_version.py diff 2.5.1
  
  python bump_version.py merge           -> bumps merge patch
  python bump_version.py merge minor
  python bump_version.py merge major
  python bump_version.py merge 2.5.1  

  python bump_version.py all             -> bumps patch for both
"""
import sys
import re

VERSION_FILE = "version.py"

APP_KEYS = {
    "viewer": "__version_viewer__",
    "diff":   "__version_diff__",
}

def read_versions() -> dict[str, str]:
    with open(VERSION_FILE) as f:
        content = f.read()
    versions = {}
    for app, key in APP_KEYS.items():
        m = re.search(rf'{key}\s*=\s*"([^"]+)"', content)
        if not m:
            raise RuntimeError(f"Could not find {key} in {VERSION_FILE}")
        versions[app] = m.group(1)
    return versions

def write_versions(versions: dict[str, str]):
    lines = []
    for app, key in APP_KEYS.items():
        lines.append(f'{key} = "{versions[app]}"')
    with open(VERSION_FILE, "w") as f:
        f.write("\n".join(lines) + "\n")

def bump(current: str, part: str) -> str:
    major, minor, patch = map(int, current.split("."))
    if part == "major":
        return f"{major + 1}.0.0"
    if part == "minor":
        return f"{major}.{minor + 1}.0"
    return f"{major}.{minor}.{patch + 1}"

if __name__ == "__main__":
    args = sys.argv[1:]
    versions = read_versions()

    print(f"Current versions -> viewer: {versions['viewer']}  diff: {versions['diff']}")

    if not args or args[0] == "all":
        part = args[1] if len(args) > 1 else "patch"
        for app in APP_KEYS:
            versions[app] = bump(versions[app], part)

    elif args[0] in APP_KEYS:
        app  = args[0]
        part = args[1] if len(args) > 1 else "patch"
        if re.match(r"^\d+\.\d+\.\d+$", part):
            versions[app] = part
        else:
            versions[app] = bump(versions[app], part)

    else:
        print(f"Unknown app '{args[0]}'. Use: viewer | diff | all")
        sys.exit(1)

    write_versions(versions)
    print(f"Updated versions  -> viewer: {versions['viewer']}  diff: {versions['diff']}")