import argparse
import os
import subprocess
import sys
from pathlib import Path

ALL_APPS = ["hex_viewer", "hex_diff_tool", "merge_tool"]

def main() -> int:
    parser = argparse.ArgumentParser(description="Build selected apps via PyInstaller + build.spec")
    parser.add_argument(
        "-a",
        "--apps",
        default="all",
        help="Comma-separated app list (hex_viewer,hex_diff_tool,merge_tool) or 'all'",
    )
    parser.add_argument(
        "-c",
        "--clean",
        action="store_true",
        help="Pass --clean to PyInstaller",
    )
    args, extra = parser.parse_known_args()

    selected = args.apps.strip().lower()
    if selected != "all":
        requested = [x.strip() for x in selected.split(",") if x.strip()]
        unknown = sorted(set(requested) - set(ALL_APPS))
        if unknown:
            print(f"Error: unknown app(s): {', '.join(unknown)}", file=sys.stderr)
            return 2
        selected = ",".join(requested)

    root = Path(__file__).resolve().parent
    spec_file = root / "build.spec"

    env = os.environ.copy()
    env["BUILD_APPS"] = selected

    cmd = [sys.executable, "-m", "PyInstaller", str(spec_file)]
    if args.clean:
        cmd.append("--clean")
    cmd.extend(extra)

    print(f"BUILD_APPS={selected}")
    print("Running:", " ".join(cmd))
    subprocess.run(cmd, cwd=root, env=env, check=True)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())