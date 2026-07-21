"""Port of ``lib/boukensha/client.rb``.

Sends the payload assembled by ``PromptBuilder`` to the backend's API over a
single HTTP POST, retrying transient network errors and retryable status
codes with exponential backoff. No third-party HTTP library — stdlib
``http.client`` only, by design (see the Ruby README's "No Dependencies"
section: the HTTP call should stay visible, not hidden behind a library).

``http.client`` is used instead of ``urllib.request`` because ``urlopen()``
raises an exception for any non-2xx response, which would fight the
retryable-status-code check below. ``http.client`` returns a plain response
object for any status, the same shape Ruby's ``Net::HTTP#request`` returns.
"""

from __future__ import annotations

import http.client
import json
import socket
import ssl
import time
from typing import Any
from urllib.parse import SplitResult, urlsplit

from boukensha.errors import ApiError
from boukensha.prompt_builder import PromptBuilder

RETRYABLE_STATUS_CODES: frozenset[int] = frozenset({408, 409, 429, 500, 502, 503, 504})

# No exact 1:1 mapping exists for Ruby's TRANSIENT_ERRORS list (EOFError,
# Errno::ECONNRESET/ECONNREFUSED, Net::OpenTimeout/ReadTimeout,
# OpenSSL::SSL::SSLError, SocketError, Timeout::Error) — these are the
# nearest stdlib equivalents. `TimeoutError` covers both connect- and
# read-timeouts since `http.client` doesn't split them the way Ruby does.
TRANSIENT_ERRORS: tuple[type[Exception], ...] = (
    ConnectionResetError,
    ConnectionRefusedError,
    TimeoutError,
    ssl.SSLError,
    socket.gaierror,
    http.client.RemoteDisconnected,
    http.client.HTTPException,
)

MAX_RETRIES = 3
BASE_RETRY_DELAY = 0.5


class Client:
    def __init__(self, builder: PromptBuilder) -> None:
        self._builder = builder

    def call(self, *, max_output_tokens: int = 1024) -> dict[str, Any]:
        url = urlsplit(self._builder.url())
        path = url.path or "/"
        if url.query:
            path = f"{path}?{url.query}"
        body = json.dumps(
            self._builder.to_api_payload(max_output_tokens=max_output_tokens)
        ).encode("utf-8")
        headers = self._builder.headers()

        response_status = -1
        response_body = b""

        for attempt in range(1, MAX_RETRIES + 2):
            connection = self._build_connection(url)
            try:
                connection.request("POST", path, body=body, headers=headers)
                response = connection.getresponse()
                response_status = response.status
                response_body = response.read()
            except TRANSIENT_ERRORS as e:
                connection.close()
                if attempt > MAX_RETRIES:
                    raise ApiError(
                        f"API request failed after {attempt} attempts: "
                        f"{type(e).__name__}: {e}"
                    ) from e
                time.sleep(self._retry_delay(attempt))
                continue
            else:
                connection.close()

            if self._is_retryable_status(response_status) and attempt <= MAX_RETRIES:
                time.sleep(self._retry_delay(attempt))
                continue

            break

        if not (200 <= response_status < 300):
            attempts_word = "attempt" if attempt == 1 else "attempts"
            raise ApiError(
                f"API request failed after {attempt} {attempts_word} "
                f"({response_status}): {response_body.decode('utf-8', errors='replace')}"
            )

        return json.loads(response_body)

    @staticmethod
    def _is_retryable_status(status: int) -> bool:
        return status in RETRYABLE_STATUS_CODES

    @staticmethod
    def _retry_delay(attempt: int) -> float:
        return BASE_RETRY_DELAY * (2 ** (attempt - 1))

    @staticmethod
    def _build_connection(url: SplitResult) -> http.client.HTTPConnection:
        if url.scheme == "https":
            return http.client.HTTPSConnection(url.hostname, url.port or 443)
        return http.client.HTTPConnection(url.hostname, url.port or 80)
