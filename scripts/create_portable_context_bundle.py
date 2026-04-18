from __future__ import annotations

import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import subprocess
from zipfile import ZIP_DEFLATED, ZipFile


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "backups"
DEFAULT_CODEX_HOME = Path(os.environ.get("CODEX_HOME") or (Path.home() / ".codex"))
ARCHIVE_PREFIX = "codex-portable-context"

DEFAULT_CODEX_DIRS = (
    "sessions",
    "archived_sessions",
    "memories",
)
DEFAULT_CODEX_FILES = (
    ".codex-global-state.json",
    "AGENTS.md",
    "config.toml",
    "session_index.jsonl",
    "state_5.sqlite",
    "state_5.sqlite-shm",
    "state_5.sqlite-wal",
    "logs_2.sqlite",
    "logs_2.sqlite-shm",
    "logs_2.sqlite-wal",
)
AUTH_FILES = (
    "auth.json",
    "cap_sid",
    "installation_id",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a portable Codex context bundle for moving to another PC."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory where the archive will be created.",
    )
    parser.add_argument(
        "--codex-home",
        type=Path,
        default=DEFAULT_CODEX_HOME,
        help="Path to the local .codex directory.",
    )
    parser.add_argument(
        "--include-auth",
        action="store_true",
        help="Also include local auth/session token files. Use only on your own trusted machines.",
    )
    return parser.parse_args()


def iter_codex_paths(codex_home: Path, include_auth: bool) -> list[Path]:
    items: list[Path] = []

    for directory_name in DEFAULT_CODEX_DIRS:
        directory = codex_home / directory_name
        if directory.exists():
            items.extend(path for path in directory.rglob("*") if path.is_file())

    for file_name in DEFAULT_CODEX_FILES:
        path = codex_home / file_name
        if path.exists() and path.is_file():
            items.append(path)

    if include_auth:
        for file_name in AUTH_FILES:
            path = codex_home / file_name
            if path.exists() and path.is_file():
                items.append(path)

    return sorted(set(items))


def build_manifest(codex_home: Path, files: list[Path], include_auth: bool) -> str:
    payload = {
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "project_root": str(PROJECT_ROOT),
        "project_git_branch": get_git_branch(PROJECT_ROOT),
        "codex_home": str(codex_home),
        "include_auth": include_auth,
        "file_count": len(files),
        "files": [path.relative_to(codex_home).as_posix() for path in files],
        "notes": [
            "Close Codex on both PCs before restore for the cleanest result.",
            "For best continuity, keep the project on the same drive letter and path.",
            "Sign in with the same OpenAI account on the other PC.",
        ],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def build_restore_note(include_auth: bool) -> str:
    auth_note = (
        "This archive includes local auth files.\n"
        "Use it only on your own trusted machine.\n"
        if include_auth
        else (
            "This archive does not include local auth files.\n"
            "Sign in to Codex manually on the new PC before restoring the bundle.\n"
        )
    )
    return (
        "Portable Codex Context Bundle\n"
        "=============================\n\n"
        "1. Close Codex on the old and new PCs.\n"
        "2. Copy the project to the same path if possible.\n"
        "3. Extract the contents of the 'codex/' folder from this archive into your new '.codex' directory.\n"
        "4. Start Codex and open the same project path.\n\n"
        f"{auth_note}\n"
    )


def get_git_branch(project_root: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(project_root), "branch", "--show-current"],
            check=True,
            capture_output=True,
            text=True,
        )
    except Exception:
        return None
    branch = result.stdout.strip()
    return branch or None


def create_bundle(output_dir: Path, codex_home: Path, include_auth: bool) -> Path:
    if not codex_home.exists():
        raise FileNotFoundError(f"Codex home not found: {codex_home}")

    files = iter_codex_paths(codex_home, include_auth)
    if not files:
        raise RuntimeError(f"No Codex context files found in: {codex_home}")

    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    archive_path = output_dir / f"{ARCHIVE_PREFIX}-{timestamp}.zip"

    with ZipFile(archive_path, "w", compression=ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, arcname=Path("codex") / path.relative_to(codex_home))
        archive.writestr("bundle_manifest.json", build_manifest(codex_home, files, include_auth))
        archive.writestr("RESTORE.txt", build_restore_note(include_auth))

    return archive_path


def main() -> None:
    args = parse_args()
    archive_path = create_bundle(
        output_dir=args.output_dir,
        codex_home=args.codex_home,
        include_auth=args.include_auth,
    )
    print(archive_path)


if __name__ == "__main__":
    main()
