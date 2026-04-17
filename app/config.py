from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os


def load_env_file(env_path: Path) -> None:
    """Load simple KEY=VALUE pairs from .env without external dependencies."""
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        os.environ.setdefault(key, value)


@dataclass(frozen=True, slots=True)
class Settings:
    bot_token: str
    database_path: Path
    polling_timeout: int = 30
    request_timeout: int = 40

    @classmethod
    def from_env(cls, project_root: Path) -> "Settings":
        load_env_file(project_root / ".env")

        token = os.getenv("BOT_TOKEN", "").strip()
        if not token:
            raise RuntimeError(
                "Не найден BOT_TOKEN. Добавь его в переменные окружения или в файл .env."
            )

        database_path = Path(
            os.getenv("DATABASE_PATH", "bot_data.sqlite3").strip() or "bot_data.sqlite3"
        )
        if not database_path.is_absolute():
            database_path = project_root / database_path

        polling_timeout = int(os.getenv("POLLING_TIMEOUT", "30"))
        request_timeout = int(os.getenv("REQUEST_TIMEOUT", "40"))
        return cls(
            bot_token=token,
            database_path=database_path,
            polling_timeout=polling_timeout,
            request_timeout=request_timeout,
        )
