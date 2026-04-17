from __future__ import annotations

import json
from typing import Any
from urllib import error, request


class TelegramAPIError(RuntimeError):
    """Raised when Telegram Bot API returns an error."""


class TelegramAPI:
    def __init__(self, token: str, request_timeout: int = 40) -> None:
        self._base_url = f"https://api.telegram.org/bot{token}"
        self._request_timeout = request_timeout

    def _call(self, method: str, payload: dict[str, Any] | None = None) -> Any:
        url = f"{self._base_url}/{method}"
        body = json.dumps(payload or {}).encode("utf-8")
        headers = {"Content-Type": "application/json; charset=utf-8"}
        req = request.Request(url, data=body, headers=headers, method="POST")

        try:
            with request.urlopen(req, timeout=self._request_timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            details = exc.read().decode("utf-8", errors="replace")
            raise TelegramAPIError(
                f"HTTP ошибка Telegram API ({exc.code}): {details}"
            ) from exc
        except error.URLError as exc:
            raise TelegramAPIError(f"Ошибка сети при запросе к Telegram API: {exc}") from exc

        if not data.get("ok"):
            raise TelegramAPIError(data.get("description", "Неизвестная ошибка Telegram API"))

        return data["result"]

    def get_updates(
        self,
        offset: int | None = None,
        timeout: int = 30,
    ) -> list[dict[str, Any]]:
        payload: dict[str, Any] = {
            "timeout": timeout,
            "allowed_updates": ["message"],
        }
        if offset is not None:
            payload["offset"] = offset
        return self._call("getUpdates", payload)

    def send_message(
        self,
        chat_id: int,
        text: str,
        reply_to_message_id: int | None = None,
        reply_markup: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "chat_id": chat_id,
            "text": text,
        }
        if reply_to_message_id is not None:
            payload["reply_to_message_id"] = reply_to_message_id
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup
        return self._call("sendMessage", payload)

    def send_photo(
        self,
        chat_id: int,
        photo_url: str,
        caption: str,
        reply_to_message_id: int | None = None,
        reply_markup: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "chat_id": chat_id,
            "photo": photo_url,
            "caption": caption,
        }
        if reply_to_message_id is not None:
            payload["reply_to_message_id"] = reply_to_message_id
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup
        return self._call("sendPhoto", payload)

    def send_media_group(
        self,
        chat_id: int,
        media: list[dict[str, Any]],
        reply_to_message_id: int | None = None,
    ) -> list[dict[str, Any]]:
        payload: dict[str, Any] = {
            "chat_id": chat_id,
            "media": media,
        }
        if reply_to_message_id is not None:
            payload["reply_to_message_id"] = reply_to_message_id
        return self._call("sendMediaGroup", payload)
