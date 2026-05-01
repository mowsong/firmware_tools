import argparse
import datetime as dt
import sys
import zipfile
from pathlib import Path

DOC_PATTERNS = ("*.md", "*.txt", "*.pdf", "*.html", "*.rst", "*.docx")


def add_files_to_zip(
    zf: zipfile.ZipFile,
    src_root: Path,
    arc_prefix: str,
    patterns: tuple[str, ...],
) -> int:
    count = 0
    seen: set[Path] = set()

    for pattern in patterns:
        for f in src_root.rglob(pattern):
            if not f.is_file():
                continue
            rel = f.relative_to(src_root)
            if rel in seen:
                continue
            seen.add(rel)
            zf.write(f, arcname=str(Path(arc_prefix) / rel))
            count += 1

    return count


def main() -> int:
    parser = argparse.ArgumentParser(description="Archive dist EXEs and docs using zlib (ZIP).")
    parser.add_argument("--project-root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--out-dir", default=None)
    parser.add_argument("--archive-name", default=None, help="Output archive name (.zip)")
    args = parser.parse_args()

    project_root = Path(args.project_root).resolve()
    dist_dir = project_root / "dist"
    docs_dir = project_root / "docs"
    out_dir = Path(args.out_dir).resolve() if args.out_dir else (project_root / "artifacts")
    out_dir.mkdir(parents=True, exist_ok=True)

    if not dist_dir.exists():
        raise FileNotFoundError(f"Missing dist folder: {dist_dir}")

    archive_name = args.archive_name
    if not archive_name:
        archive_name = f"hex_tools_{dt.datetime.now():%Y%m%d_%H%M%S}.zip"
    if not archive_name.lower().endswith(".zip"):
        archive_name += ".zip"

    archive_path = out_dir / archive_name

    with zipfile.ZipFile(
        archive_path,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,  # zlib/deflate
        compresslevel=9,
    ) as zf:
        exe_count = add_files_to_zip(zf, dist_dir, "dist", ("*.exe",))
        doc_count = add_files_to_zip(zf, docs_dir, "docs", DOC_PATTERNS) if docs_dir.exists() else 0

    print(f"Created archive: {archive_path}")
    print(f"Included: {exe_count} exe(s), {doc_count} doc file(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())