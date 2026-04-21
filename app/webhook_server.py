from __future__ import annotations

from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import logging
import threading
from typing import Any, Callable
from urllib.parse import urlsplit


UpdateHandler = Callable[[dict[str, Any]], None]
TickHandler = Callable[[], None]


class TelegramWebhookServer:
    def __init__(
        self,
        host: str,
        port: int,
        webhook_path: str,
        on_update: UpdateHandler,
        on_tick: TickHandler | None = None,
        tick_interval: int = 30,
        secret_token: str | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self._host = host
        self._port = port
        self._webhook_path = webhook_path
        self._on_update = on_update
        self._on_tick = on_tick
        self._tick_interval = max(1, tick_interval)
        self._secret_token = secret_token
        self._logger = logger or logging.getLogger(__name__)
        self._stop_event = threading.Event()
        self._ticker: threading.Thread | None = None
        if self._on_tick is not None:
            self._ticker = threading.Thread(
                target=self._ticker_loop,
                name="subscription-dispatcher",
                daemon=True,
            )

        handler_class = self._build_handler()
        self._server = ThreadingHTTPServer((self._host, self._port), handler_class)
        self._server.daemon_threads = True

    @property
    def bind_address(self) -> tuple[str, int]:
        return self._host, self._port

    def serve_forever(self) -> None:
        if self._ticker is not None:
            self._ticker.start()
        self._server.serve_forever()

    def shutdown(self) -> None:
        self._stop_event.set()
        self._server.shutdown()
        self._server.server_close()
        if self._ticker is not None:
            self._ticker.join(timeout=2)

    def _build_handler(self) -> type[BaseHTTPRequestHandler]:
        on_update = self._on_update
        webhook_path = self._webhook_path
        secret_token = self._secret_token
        logger = self._logger

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                if urlsplit(self.path).path == "/healthz":
                    self._write_json(HTTPStatus.OK, {"ok": True})
                    return
                self._write_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "Not found"})

            def do_POST(self) -> None:  # noqa: N802
                if urlsplit(self.path).path != webhook_path:
                    self._write_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "Not found"})
                    return

                if secret_token is not None:
                    header_secret = self.headers.get("X-Telegram-Bot-Api-Secret-Token")
                    if header_secret != secret_token:
                        logger.warning("Webhook rejected due to invalid secret token header")
                        self._write_json(HTTPStatus.FORBIDDEN, {"ok": False, "error": "Forbidden"})
                        return

                try:
                    content_length = int(self.headers.get("Content-Length", "0"))
                except ValueError:
                    self._write_json(
                        HTTPStatus.BAD_REQUEST,
                        {"ok": False, "error": "Invalid Content-Length"},
                    )
                    return

                if content_length <= 0:
                    self._write_json(
                        HTTPStatus.BAD_REQUEST,
                        {"ok": False, "error": "Empty request body"},
                    )
                    return

                try:
                    payload = json.loads(self.rfile.read(content_length).decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    self._write_json(
                        HTTPStatus.BAD_REQUEST,
                        {"ok": False, "error": "Invalid JSON payload"},
                    )
                    return

                if not isinstance(payload, dict):
                    self._write_json(
                        HTTPStatus.BAD_REQUEST,
                        {"ok": False, "error": "Webhook payload must be an object"},
                    )
                    return

                try:
                    on_update(payload)
                except Exception:
                    logger.exception("Webhook payload could not be stored")
                    self._write_json(
                        HTTPStatus.INTERNAL_SERVER_ERROR,
                        {"ok": False, "error": "Webhook processing failed"},
                    )
                    return

                self._write_json(HTTPStatus.OK, {"ok": True})

            def log_message(self, format: str, *args: object) -> None:
                logger.debug("Webhook HTTP: " + format, *args)

            def _write_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
                body = json.dumps(payload).encode("utf-8")
                self.send_response(int(status))
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        return Handler

    def _ticker_loop(self) -> None:
        if self._on_tick is None:
            return

        while not self._stop_event.wait(self._tick_interval):
            try:
                self._on_tick()
            except Exception:
                self._logger.exception("Unhandled error while running background scheduler tick")
