import argparse
import datetime as dt
import sys
import zipfile
from pathlib import Path

SOURCE_PATTERNS = (
    "*.py",
    "*.pyi",
    "*.c",
    "*.h",
    "*.cpp",
    "*.hpp",
    "*.json",
    "*.toml",
    "*.yaml",
    "*.yml",
    "*.ini",
    "*.cfg",
)

ICON_PATTERNS = ("*.ico", "*.png", "*.svg", "*.icns", "*.bmp")
DOC_PATTERNS = ("*.md", "*.txt", "*.pdf", "*.html", "*.rst", "*.docx")

EXCLUDE_DIRS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    "dist",
    "build",
    "artifacts",
    ".mypy_cache",
    ".pytest_cache",
}


def is_excluded(path: Path, project_root: Path) -> bool:
    rel_parts = path.relative_to(project_root).parts
    return any(part in EXCLUDE_DIRS for part in rel_parts)


def add_files_to_zip(
    zf: zipfile.ZipFile,
    project_root: Path,
    patterns: tuple[str, ...],
) -> int:
    count = 0
    seen: set[Path] = set()

    for pattern in patterns:
        for f in project_root.rglob(pattern):
            if not f.is_file():
                continue
            if is_excluded(f.parent, project_root):
                continue

            rel = f.relative_to(project_root)
            if rel in seen:
                continue

            seen.add(rel)
            zf.write(f, arcname=str(rel))
            count += 1

    return count


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Archive source code, icons, and docs into a ZIP (zlib/deflate)."
    )
    parser.add_argument("--project-root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--out-dir", default=None)
    parser.add_argument("--archive-name", default=None, help="Output archive name (.zip)")
    args = parser.parse_args()

    project_root = Path(args.project_root).resolve()
    out_dir = Path(args.out_dir).resolve() if args.out_dir else (project_root / "artifacts")
    out_dir.mkdir(parents=True, exist_ok=True)

    archive_name = args.archive_name
    if not archive_name:
        archive_name = f"hex_tools_source_{dt.datetime.now():%Y%m%d_%H%M%S}.zip"
    if not archive_name.lower().endswith(".zip"):
        archive_name += ".zip"

    archive_path = out_dir / archive_name

    with zipfile.ZipFile(
        archive_path,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
    ) as zf:
        src_count = add_files_to_zip(zf, project_root, SOURCE_PATTERNS)
        icon_count = add_files_to_zip(zf, project_root, ICON_PATTERNS)
        doc_count = add_files_to_zip(zf, project_root, DOC_PATTERNS)

    print(f"Created archive: {archive_path}")
    print(f"Included: {src_count} source file(s), {icon_count} icon file(s), {doc_count} doc file(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())