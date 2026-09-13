"""Create a platform archive from the PyInstaller output."""
from __future__ import annotations

import argparse
import sys
import tarfile
import zipfile
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--platform", required=True, choices=("macos", "windows", "linux"))
    parser.add_argument("--version", default="dev")
    parser.add_argument("--dist", type=Path, default=Path("build/dist"))
    parser.add_argument("--output", type=Path, default=Path("build/packages"))
    args = parser.parse_args()

    executable_name = "ex-skill.app" if args.platform == "macos" else "ex-skill.exe" if args.platform == "windows" else "ex-skill"
    source = args.dist / executable_name
    if not source.exists():
        raise SystemExit(f"PyInstaller output not found: {source}")

    archive_name = f"ex-skill-{args.platform}-{args.version}"
    args.output.mkdir(parents=True, exist_ok=True)

    if args.platform == "linux":
        archive = args.output / f"{archive_name}.tar.gz"
        with tarfile.open(archive, "w:gz") as tar:
            tar.add(source, arcname=source.name)
    else:
        archive = args.output / f"{archive_name}.zip"
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zipped:
            if source.is_dir():
                for path in source.rglob("*"):
                    if path.is_file():
                        zipped.write(path, path.relative_to(args.dist))
            else:
                zipped.write(source, source.name)

    print(archive)
    return 0


if __name__ == "__main__":
    sys.exit(main())