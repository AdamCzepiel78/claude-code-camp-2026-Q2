#!/usr/bin/env python3
"""
Deterministic connection/login handler for the tbaMUD instance at localhost:4000.

Exists so the agent never has to improvise a telnet/socket script or guess the
login sequence -- it just calls this with a list of in-game commands and gets
back the cleaned transcript.

Usage:
    python3 mud_client.py "look" "north" "look"
    python3 mud_client.py --keep-color "score"
    python3 mud_client.py --quit               # run no commands, then fully log out

By default the socket is closed after the commands run WITHOUT sending
"quit" -- this leaves the character link-dead in the game world (same as a
client crashing), so the next invocation reconnects and picks up exactly
where it left off. Pass --quit only when you actually want to end the
session and return the character to the character menu.
"""
import argparse
import re
import socket
import sys
import time

HOST = "localhost"
PORT = 4000
USERNAME = "dummy"
PASSWORD = "helloworld"

IAC = 255
SB = 250
SE = 240
WILL, WONT, DO, DONT = 251, 252, 253, 254

ANSI_RE = re.compile(rb"\x1b\[[0-9;]*[A-Za-z]")


def strip_telnet(data: bytes) -> bytes:
    """Remove telnet IAC negotiation/subnegotiation sequences from a stream."""
    out = bytearray()
    i = 0
    n = len(data)
    while i < n:
        b = data[i]
        if b == IAC and i + 1 < n:
            cmd = data[i + 1]
            if cmd == SB:
                j = data.find(bytes([IAC, SE]), i + 2)
                i = j + 2 if j != -1 else n
                continue
            if cmd in (WILL, WONT, DO, DONT):
                i += 3
                continue
            i += 2
            continue
        out.append(b)
        i += 1
    return bytes(out)


def clean(data: bytes, keep_color: bool) -> str:
    data = strip_telnet(data)
    if not keep_color:
        data = ANSI_RE.sub(b"", data)
    return data.decode("latin-1", errors="replace")


class MudSession:
    def __init__(self, host, port, idle=0.4, max_wait=5):
        self.idle = idle
        self.max_wait = max_wait
        self.sock = socket.create_connection((host, port), timeout=10)

    def _read_until_idle(self, max_wait=None) -> bytes:
        self.sock.settimeout(self.idle)
        buf = b""
        start = time.time()
        max_wait = self.max_wait if max_wait is None else max_wait
        while True:
            try:
                chunk = self.sock.recv(4096)
                if not chunk:
                    break
                buf += chunk
            except socket.timeout:
                break
            if time.time() - start > max_wait:
                break
        return buf

    def _read_until(self, markers, timeout=10.0) -> bytes:
        """Accumulate input until the cleaned text contains one of `markers`.

        The banner does client-detection negotiation with a >1s gap in the
        middle of it, so idle-based reading alone races the prompt and can
        send credentials before the server is actually ready to read them.
        Waiting for the literal prompt text avoids that race.
        """
        self.sock.settimeout(0.2)
        buf = b""
        start = time.time()
        while time.time() - start < timeout:
            try:
                chunk = self.sock.recv(4096)
                if not chunk:
                    break
                buf += chunk
            except socket.timeout:
                pass
            text = clean(buf, keep_color=False)
            if any(m in text for m in markers):
                break
        return buf

    def _send(self, line: str):
        self.sock.sendall(line.encode("latin-1") + b"\r\n")

    def login(self, username: str, password: str, keep_color: bool) -> str:
        # The client-detection banner has a >1s gap baked into it, so this
        # first wait must be marker-based rather than idle-based or the
        # username can be sent before the server is ready to read it.
        transcript = self._read_until(["name do you wish"])
        self._send(username)
        transcript += self._read_until(["assword:"])
        self._send(password)

        # From here on, walk through whatever sequence of prompts the server
        # throws at us (MOTD "press return" gates, the reconnect message, or
        # the numbered character menu) until the in-game status bar shows up.
        # Reacting to prompt text -- rather than assuming a fixed sequence --
        # means this works whether the previous session ended by a clean
        # "quit" (numbered menu) or by just dropping the link (straight back
        # into the game).
        game_prompt = re.compile(r"\d+H\s+\d+M\s+\d+V")
        for _ in range(8):
            chunk = self._read_until_idle(max_wait=3)
            transcript += chunk
            tail = clean(transcript, keep_color=False)[-400:]
            if game_prompt.search(tail):
                break
            lower = tail.lower()
            if "make your choice" in lower or "enter the game" in lower:
                self._send("1")
            elif "press return" in lower or "hit return" in lower or "continue]" in lower:
                self._send("")
            elif not chunk:
                # Nothing new arrived and no known prompt matched -- give up
                # rather than spin; the caller can inspect the raw transcript.
                break

        return clean(transcript, keep_color)

    def send_command(self, command: str, keep_color: bool) -> str:
        self._send(command)
        return clean(self._read_until_idle(), keep_color)

    def quit(self, keep_color: bool) -> str:
        out = self.send_command("quit", keep_color)
        if "Make your choice" in out:
            out += self.send_command("0", keep_color)
        return out

    def close(self):
        self.sock.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("commands", nargs="*", help="in-game commands to run in order")
    parser.add_argument("--host", default=HOST)
    parser.add_argument("--port", type=int, default=PORT)
    parser.add_argument("--user", default=USERNAME)
    parser.add_argument("--password", default=PASSWORD)
    parser.add_argument("--keep-color", action="store_true", help="keep ANSI color codes in output")
    parser.add_argument("--quit", action="store_true", help="fully log out (send quit) after running commands")
    parser.add_argument("--idle", type=float, default=0.4, help="seconds of silence before assuming a reply is finished")
    parser.add_argument("--max-wait", type=float, default=5.0, help="hard cap in seconds to wait for any single reply")
    args = parser.parse_args()

    try:
        session = MudSession(args.host, args.port, idle=args.idle, max_wait=args.max_wait)
    except (ConnectionRefusedError, socket.timeout, OSError) as exc:
        print(f"Could not connect to {args.host}:{args.port} -- {exc}", file=sys.stderr)
        sys.exit(1)

    try:
        print("=== login ===")
        print(session.login(args.user, args.password, args.keep_color))

        for cmd in args.commands:
            print(f"\n> {cmd}")
            print(session.send_command(cmd, args.keep_color))

        if args.quit:
            print("\n> quit")
            print(session.quit(args.keep_color))
    finally:
        session.close()


if __name__ == "__main__":
    main()
