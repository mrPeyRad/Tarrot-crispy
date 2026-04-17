from __future__ import annotations

from pathlib import Path

from app.bot import TarotHoroscopeBot


def main() -> None:
    project_root = Path(__file__).resolve().parent
    bot = TarotHoroscopeBot.from_project_root(project_root)
    bot.run()


if __name__ == "__main__":
    main()
