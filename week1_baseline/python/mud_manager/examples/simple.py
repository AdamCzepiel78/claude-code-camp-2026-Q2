#!/usr/bin/env python3
"""Port of ``week1_baseline/mud_manager_mcp_mcp/examples/simple.rb``.

Minimal end-to-end demo of the ``mud_manager`` library on its own, with no
``boukensha`` agent involved: open a session, log in, send one command, print
the response, close.

    python3 examples/simple.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# python/ (this file's grandparent's parent) is where the `mud_manager`
# package lives, as a sibling of every boukensha step directory.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import mud_manager  # noqa: E402

HOST = "localhost"
PORT = 4000
USERNAME = "dummy"
PASSWORD = "helloworld"


def main() -> None:
    session = mud_manager.Session(host=HOST, port=PORT)
    session.open()

    session.login(USERNAME, PASSWORD)

    command = mud_manager.primitives.look()
    print(command)
    session.send_command(command)

    output = session.read_until_quiet()
    print(output)

    session.close()


if __name__ == "__main__":
    main()
