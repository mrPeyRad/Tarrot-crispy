from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKUPS_DIR = PROJECT_ROOT / "backups"
ARCHIVE_PREFIX = "tarrot-crispy-backup"
EXCLUDED_DIRS = {".git", "__pycache__", "backups", "runtime"}
EXCLUDED_SUFFIXES = {".log", ".pyc"}


def _should_skip(path: Path) -> bool:
    if path.is_dir():
        return path.name in EXCLUDED_DIRS

    if any(part in EXCLUDED_DIRS for part in path.relative_to(PROJECT_ROOT).parts[:-1]):
        return True

    return path.suffix.lower() in EXCLUDED_SUFFIXES


def _iter_backup_files() -> list[Path]:
    files: list[Path] = []
    for path in PROJECT_ROOT.rglob("*"):
        if not path.is_file():
            continue
        if _should_skip(path):
            continue
        files.append(path)
    return sorted(files)


def _build_manifest(files: list[Path], archive_name: str) -> str:
    payload = {
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "archive_name": archive_name,
        "project_root": str(PROJECT_ROOT),
        "file_count": len(files),
        "files": [path.relative_to(PROJECT_ROOT).as_posix() for path in files],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def create_backup() -> Path:
    BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    archive_path = BACKUPS_DIR / f"{ARCHIVE_PREFIX}-{timestamp}.zip"
    files = _iter_backup_files()

    with ZipFile(archive_path, "w", compression=ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, arcname=path.relative_to(PROJECT_ROOT))
        archive.writestr("backup_manifest.json", _build_manifest(files, archive_path.name))

    return archive_path


def main() -> None:
    archive_path = create_backup()
    print(archive_path)


if __name__ == "__main__":
    main()
