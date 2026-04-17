from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os


DEFAULT_BOT_DESCRIPTION = (
    "Привет. Я помогаю с таро, гороскопами, рунами и небольшими мистическими ритуалами.\n"
    "Напиши /start, чтобы открыть быстрое меню."
)
DEFAULT_BOT_SHORT_DESCRIPTION = (
    "Таро, гороскопы, руны и мистические подсказки на каждый день."
)


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
    bot_username: str | None
    bot_name: str | None
    bot_description: str
    bot_short_description: str
    database_path: Path
    openai_api_key: str | None
    openai_model: str
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

        raw_username = os.getenv("BOT_USERNAME", "").strip()
        bot_username = raw_username or None
        if bot_username and not bot_username.startswith("@"):
            bot_username = f"@{bot_username}"

        bot_name = os.getenv("BOT_NAME", "").strip() or None
        bot_description = (
            os.getenv("BOT_DESCRIPTION", "").strip() or DEFAULT_BOT_DESCRIPTION
        )
        bot_short_description = (
            os.getenv("BOT_SHORT_DESCRIPTION", "").strip()
            or DEFAULT_BOT_SHORT_DESCRIPTION
        )

        database_path = Path(
            os.getenv("DATABASE_PATH", "bot_data.sqlite3").strip() or "bot_data.sqlite3"
        )
        if not database_path.is_absolute():
            database_path = project_root / database_path

        openai_api_key = os.getenv("OPENAI_API_KEY", "").strip() or None
        openai_model = os.getenv("OPENAI_MODEL", "gpt-5-mini").strip() or "gpt-5-mini"
        polling_timeout = int(os.getenv("POLLING_TIMEOUT", "30"))
        request_timeout = int(os.getenv("REQUEST_TIMEOUT", "40"))
        return cls(
            bot_token=token,
            bot_username=bot_username,
            bot_name=bot_name,
            bot_description=bot_description,
            bot_short_description=bot_short_description,
            database_path=database_path,
            openai_api_key=openai_api_key,
            openai_model=openai_model,
            polling_timeout=polling_timeout,
            request_timeout=request_timeout,
        )
