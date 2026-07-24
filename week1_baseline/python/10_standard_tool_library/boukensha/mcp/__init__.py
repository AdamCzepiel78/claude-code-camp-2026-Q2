"""Port of ``lib/boukensha/mcp.rb`` — BOUKENSHA's Model Context Protocol client side.

- :class:`~boukensha.mcp.client.Client` — the protocol client: spawn a server,
  handshake, call tools.
- :mod:`boukensha.mcp.registrar` — turn one server's advertised tools into agent
  tools.
- :mod:`boukensha.mcp.servers` — drive several servers at once, namespacing
  collisions.

:mod:`boukensha.tools.mcp` is the public entry point that sits alongside
:mod:`boukensha.tools.file_system`; :mod:`boukensha.tools.mud_mcp` is a preset
over it. Everything here is domain-free — the MUD is one server among any number.
"""

from __future__ import annotations

from boukensha.mcp import registrar, servers
from boukensha.mcp.client import Client, Error, ProtocolError

__all__ = ["Client", "Error", "ProtocolError", "registrar", "servers"]
