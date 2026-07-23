"""Port of ``mud_manager/lib/mud_manager/session.rb``.

Long-lived telnet connection to a CircleMUD server.

A background thread continuously drains the socket into an internal buffer,
stripping telnet IAC negotiation bytes. The agent loop sends a command and then
calls ``read_until_quiet`` (or ``read_until`` for a known prompt) to collect both
the command's response and any async chatter that arrived in the meantime.
"""

from __future__ import annotations

import re
import socket
import threading
import time
from typing import Any

DEFAULT_HOST = "localhost"
DEFAULT_PORT = 4000
DEFAULT_TIMEOUT = 10.0

# Telnet protocol bytes we recognise. We don't negotiate — we just consume and
# discard IAC sequences so they don't pollute the buffer.
_IAC = 0xFF
_DONT = 0xFE
_DO = 0xFD
_WONT = 0xFC
_WILL = 0xFB
_SB = 0xFA
_SE = 0xF0

# CircleMUD terminates every command response with a prompt that ends in "> "
# (greater-than space). Waiting for that sentinel is faster and more
# deterministic than relying on a silence window — it returns as soon as the
# server signals it has finished processing the command.
PROMPT_SENTINEL = "> "


class SessionError(Exception):
    pass


class ConnectionError(SessionError):  # noqa: A001 - matches Ruby's naming
    pass


class LoginError(SessionError):
    pass


class MudTimeoutError(SessionError):
    """Named to avoid shadowing the builtin ``TimeoutError``."""


class Session:
    def __init__(
        self,
        *,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self.host = host
        self.port = port
        self._timeout = timeout
        self._socket: socket.socket | None = None
        self._reader: threading.Thread | None = None
        self._buffer = ""
        self._lock = threading.Lock()
        self._cv = threading.Condition(self._lock)
        self._closed = False
        self._last_recv_at: float | None = None

    def open(self) -> "Session":
        if self._socket is not None:
            raise SessionError("already open")
        try:
            self._socket = socket.create_connection((self.host, self.port))
        except OSError as e:
            raise ConnectionError(f"connect {self.host}:{self.port} failed: {e}") from e
        self._closed = False
        self._start_reader()
        return self

    def is_open(self) -> bool:
        return self._socket is not None and not self._closed

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            if self._socket is not None:
                self._socket.close()
        except OSError:
            pass  # already closed / broken — fine
        if self._reader is not None:
            self._reader.join(1)
        self._socket = None
        self._reader = None

    def send_command(self, command: Any = None) -> str:
        """Send a command. Accepts a string, a ``Primitives.Command``, ``None``
        (bare return/enter), or anything convertible via ``str()``. A trailing
        newline is appended.
        """
        if not self.is_open():
            raise SessionError("session not open")
        if command is None:
            line = ""
        elif hasattr(command, "raw"):
            line = command.raw
        else:
            line = str(command)
        assert self._socket is not None
        self._socket.sendall((line + "\r\n").encode("utf-8"))
        return line

    def drain(self) -> str:
        """Drain whatever is currently buffered and return it. Non-blocking."""
        with self._lock:
            out, self._buffer = self._buffer, ""
            return out

    def read_until_quiet(self, quiet_seconds: float = 1.0, *, timeout: float | None = None) -> str:
        """Block until ``quiet_seconds`` have elapsed with no new bytes arriving,
        or ``timeout`` total seconds pass. Returns whatever accumulated.
        """
        if not self.is_open():
            raise SessionError("session not open")
        deadline = time.monotonic() + (timeout if timeout is not None else self._timeout)
        with self._lock:
            while True:
                remaining_total = deadline - time.monotonic()
                if remaining_total <= 0:
                    break

                if (
                    self._last_recv_at is not None
                    and (time.monotonic() - self._last_recv_at) >= quiet_seconds
                    and self._buffer
                ):
                    break

                if self._last_recv_at is not None and self._buffer:
                    wait_for = quiet_seconds - (time.monotonic() - self._last_recv_at)
                else:
                    wait_for = remaining_total
                wait_for = min(wait_for, remaining_total)
                if wait_for <= 0:
                    break
                self._cv.wait(wait_for)

            out, self._buffer = self._buffer, ""
            return out

    def read_until(self, pattern: str | re.Pattern[str], *, timeout: float | None = None) -> str:
        """Block until the buffer contains the given pattern (str or compiled
        regex), then return everything up to and including the match. Raises
        :class:`MudTimeoutError` if ``timeout`` seconds pass without a match.
        """
        if not self.is_open():
            raise SessionError("session not open")
        regexp = pattern if isinstance(pattern, re.Pattern) else re.compile(re.escape(pattern))
        deadline = time.monotonic() + (timeout if timeout is not None else self._timeout)
        with self._lock:
            while True:
                m = regexp.search(self._buffer)
                if m:
                    cut = m.end()
                    out = self._buffer[:cut]
                    self._buffer = self._buffer[cut:]
                    return out
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise MudTimeoutError(f"read_until {pattern!r} after {timeout}s")
                if self._closed:
                    raise ConnectionError("socket closed while waiting")
                self._cv.wait(remaining)

    def read_until_prompt(self, *, timeout: float | None = None) -> str:
        try:
            return self.read_until(PROMPT_SENTINEL, timeout=timeout)
        except MudTimeoutError:
            print(
                "[mud_manager.Session] prompt not detected within timeout; "
                "returning buffered content"
            )
            return self.drain()

    def login(self, username: str, password: str) -> str:
        """Walk the CircleMUD login dance."""
        self.read_until(re.compile(r"By what name do you wish to be known.*\?", re.IGNORECASE))

        self.send_command(username)
        self.read_until(re.compile(r"Password", re.IGNORECASE))

        self.send_command(password)
        output = self.read_until(re.compile(r"Welcome|Reconnecting|Wrong password", re.IGNORECASE))

        if re.search(r"Reconnecting", output, re.IGNORECASE):
            pass  # already in-world, skip menu
        elif re.search(r"Welcome", output, re.IGNORECASE):
            self.send_command(None)  # enter for main menu
            self.send_command(1)  # enter the game
            self.read_until_quiet()
        elif re.search(r"Wrong password", output, re.IGNORECASE):
            raise LoginError("wrong password")

        return output

    # ----- internals -----

    def _start_reader(self) -> None:
        def reader_loop() -> None:
            assert self._socket is not None
            try:
                while True:
                    try:
                        chunk = self._socket.recv(4096)
                    except OSError:
                        break
                    if not chunk:
                        break
                    text = self._strip_iac(chunk)
                    if text:
                        with self._lock:
                            self._buffer += text
                            self._last_recv_at = time.monotonic()
                            self._cv.notify_all()
            finally:
                with self._lock:
                    self._closed = True
                    self._cv.notify_all()

        self._reader = threading.Thread(target=reader_loop, daemon=True)
        self._reader.start()

    @staticmethod
    def _strip_iac(data: bytes) -> str:
        """Telnet protocol IAC stripper. The MUD may interleave:
        IAC (WILL|WONT|DO|DONT) <option>   — 3 bytes
        IAC SB <option> ... IAC SE         — variable
        IAC IAC                            — literal 0xFF byte
        We discard all of them. CircleMUD's negotiation is mostly echo
        toggling around the password prompt, which we don't honor.
        """
        out = bytearray()
        i = 0
        n = len(data)
        while i < n:
            b = data[i]
            if b == _IAC:
                nxt = data[i + 1] if i + 1 < n else None
                if nxt is None:
                    break
                if nxt == _IAC:
                    out.append(0xFF)
                    i += 2
                elif nxt in (_WILL, _WONT, _DO, _DONT):
                    i += 3
                elif nxt == _SB:
                    j = i + 2
                    while j < n and not (data[j] == _IAC and j + 1 < n and data[j + 1] == _SE):
                        j += 1
                    i = j + 2
                else:
                    i += 2
            else:
                out.append(b)
                i += 1
        return out.decode("utf-8", errors="replace")
