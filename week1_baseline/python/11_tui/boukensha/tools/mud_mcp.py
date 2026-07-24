"""Port of ``lib/boukensha/tools/mud_mcp.rb``.

MUD preset over the generic :mod:`boukensha.tools.mcp`.

Everything that makes this "the MUD one" lives here, and it is all
configuration: which binary to start, which environment variables carry the
credentials, and which tool is worth calling eagerly. The registration
machinery — discovery, filtering, argument pruning, cleanup — is generic and
lives in :mod:`boukensha.tools.mcp`.

That split is the point. The agent is not coupled to MUDs; it is coupled to MCP,
and this file is the handful of lines that aim it at one particular server.

Note the trade this path makes: it needs Ruby on PATH to run the server, which
is why the pure-Python ``tools/mud.py`` is kept as a fallback (``mud_mcp=False``).
"""

from __future__ import annotations

import os
import shlex
from pathlib import Path

from boukensha.mcp.client import Client
from boukensha.registry import Registry
from boukensha.tools import mcp as Mcp

# week1_baseline/mud_manager_mcp/bin/mud_manager_mcp, relative to this file:
# tools -> boukensha -> 10_standard_tool_library -> python -> week1_baseline
# Preferred over the gem-installed executable so the step runs straight from a
# checkout, with no `gem install` step.
DEFAULT_SERVER = Path(__file__).resolve().parents[4] / "mud_manager_mcp" / "bin" / "mud_manager_mcp"

# The MUD login costs ~6s. Paying it at registration keeps it out of the agent's
# first tool call. The server also states this in its handshake instructions, so
# an agent would get there on its own — this only saves the turn.
BOOTSTRAP_TOOL = "session_open"


def register(
    registry: Registry,
    *,
    host: str | None = None,
    port: int | None = None,
    name: str | None = None,
    password: str | None = None,
    command: list[str] | None = None,
    autoconnect: bool = True,
    only: list[str] | None = None,
    except_: list[str] | None = None,
    debug: bool = False,
) -> Client:
    return Mcp.register(
        registry,
        command=command or _default_command(),
        env=_server_env(host=host, port=port, name=name, password=password, debug=debug),
        only=only,
        except_=except_,
        after_connect=BOOTSTRAP_TOOL if autoconnect else None,
        debug=debug,
    )


# ---------- internals --------------------------------------------------------


def _default_command() -> list[str]:
    override = os.environ.get("BOUKENSHA_MUD_MCP_COMMAND")
    if override:
        return shlex.split(override)
    return ["ruby", str(DEFAULT_SERVER)]


def _server_env(
    *,
    host: str | None,
    port: int | None,
    name: str | None,
    password: str | None,
    debug: bool,
) -> dict[str, str | None]:
    pairs: dict[str, str | None] = {
        "MUD_HOST": host,
        "MUD_PORT": None if port is None else str(port),
        "MUD_NAME": name,
        "MUD_PASSWORD": password,
    }
    env: dict[str, str | None] = {k: v for k, v in pairs.items() if v is not None}

    # One debug switch, not two: the client's `debug` forwards the server's
    # stderr, and this makes the server actually say something.
    if debug:
        env["MUD_MCP_DEBUG"] = "1"

    # The server is a standalone Ruby script with no Gemfile. If this process was
    # itself started under `bundle exec`, the child would inherit BUNDLE_*/RUBYOPT,
    # re-initialise bundler and bury its own logging under constant-redefinition
    # warnings. None removes the variable from the child.
    for key in ("BUNDLE_GEMFILE", "BUNDLE_BIN_PATH", "BUNDLE_PATH", "RUBYOPT"):
        env[key] = None

    return env
