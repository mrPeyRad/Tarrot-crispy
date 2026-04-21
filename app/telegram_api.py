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

    def _perform_request(self, method: str, data: bytes, headers: dict[str, str]) -> Any:
        url = f"{self._base_url}/{method}"
        req = request.Request(url, data=data, headers=headers, method="POST")

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

    def _call(self, method: str, payload: dict[str, Any] | None = None) -> Any:
        body = json.dumps(payload or {}).encode("utf-8")
        headers = {"Content-Type": "application/json; charset=utf-8"}
        return self._perform_request(method, body, headers)

    def _call_multipart(
        self,
        method: str,
        fields: dict[str, str],
        files: dict[str, tuple[str, bytes, str]],
    ) -> Any:
        boundary = "----CodexTelegramBoundary7MA4YWxkTrZu0gW"
        body = bytearray()
        for key, value in fields.items():
            body.extend(f"--{boundary}\r\n".encode("utf-8"))
            body.extend(
                f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode("utf-8")
            )
            body.extend(value.encode("utf-8"))
            body.extend(b"\r\n")

        for key, (filename, content, content_type) in files.items():
            body.extend(f"--{boundary}\r\n".encode("utf-8"))
            body.extend(
                (
                    f'Content-Disposition: form-data; name="{key}"; filename="{filename}"\r\n'
                    f"Content-Type: {content_type}\r\n\r\n"
                ).encode("utf-8")
            )
            body.extend(content)
            body.extend(b"\r\n")

        body.extend(f"--{boundary}--\r\n".encode("utf-8"))
        headers = {"Content-Type": f"multipart/form-data; boundary={boundary}"}
        return self._perform_request(method, bytes(body), headers)

    def get_me(self) -> dict[str, Any]:
        return self._call("getMe")

    def set_my_commands(
        self,
        commands: list[dict[str, str]],
    ) -> bool:
        return self._call("setMyCommands", {"commands": commands})

    def set_my_name(
        self,
        name: str,
        language_code: str | None = None,
    ) -> bool:
        payload: dict[str, Any] = {"name": name}
        if language_code is not None:
            payload["language_code"] = language_code
        return self._call("setMyName", payload)

    def set_my_description(
        self,
        description: str,
        language_code: str | None = None,
    ) -> bool:
        payload: dict[str, Any] = {"description": description}
        if language_code is not None:
            payload["language_code"] = language_code
        return self._call("setMyDescription", payload)

    def set_my_short_description(
        self,
        short_description: str,
        language_code: str | None = None,
    ) -> bool:
        payload: dict[str, Any] = {"short_description": short_description}
        if language_code is not None:
            payload["language_code"] = language_code
        return self._call("setMyShortDescription", payload)

    def set_chat_menu_button(
        self,
        menu_button: dict[str, Any],
        chat_id: int | None = None,
    ) -> bool:
        payload: dict[str, Any] = {"menu_button": menu_button}
        if chat_id is not None:
            payload["chat_id"] = chat_id
        return self._call("setChatMenuButton", payload)

    def set_webhook(
        self,
        url: str,
        secret_token: str | None = None,
        drop_pending_updates: bool = False,
        allowed_updates: list[str] | None = None,
    ) -> bool:
        payload: dict[str, Any] = {
            "url": url,
            "drop_pending_updates": drop_pending_updates,
            "allowed_updates": allowed_updates or ["message"],
        }
        if secret_token is not None:
            payload["secret_token"] = secret_token
        return self._call("setWebhook", payload)

    def delete_webhook(
        self,
        drop_pending_updates: bool = False,
    ) -> bool:
        return self._call(
            "deleteWebhook",
            {"drop_pending_updates": drop_pending_updates},
        )

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
        photo_url: str | None = None,
        caption: str = "",
        reply_to_message_id: int | None = None,
        reply_markup: dict[str, Any] | None = None,
        photo_bytes: bytes | None = None,
        filename: str = "card.png",
    ) -> dict[str, Any]:
        if photo_url is None and photo_bytes is None:
            raise ValueError("Нужно передать либо photo_url, либо photo_bytes.")

        if photo_bytes is not None:
            fields: dict[str, str] = {
                "chat_id": str(chat_id),
                "caption": caption,
            }
            if reply_to_message_id is not None:
                fields["reply_to_message_id"] = str(reply_to_message_id)
            if reply_markup is not None:
                fields["reply_markup"] = json.dumps(reply_markup, ensure_ascii=False)
            return self._call_multipart(
                "sendPhoto",
                fields=fields,
                files={"photo": (filename, photo_bytes, "image/png")},
            )

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
