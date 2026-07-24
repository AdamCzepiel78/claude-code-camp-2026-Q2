# Plan: a generic MCP server + `Boukensha::MCP`

Status: **implemented and verified** (see "Status — 2026-07-24" below)
Date: 2026-07-24

## Context

[`generic_interfacing.md`](generic_interfacing.md) solved the client side. The
agent no longer restates a MUD tool surface per language: `Tools::Mcp` (109 LOC
Ruby / 134 Python) discovers whatever an MCP server advertises, and `MudMcp`
shrank to an ~85-line preset holding only the binary path, the `MUD_*` env
mapping and `after_connect: "session_open"`. Proven domain-free by driving an
unrelated notes server from both languages.

The **server side never got the same treatment.** `mud_manager_mcp` still bakes
its own identity, its instructions and its tool module directly into the JSON-RPC
transport — which means a bootcamper who wants to *write* an MCP server (rather
than consume one) has nothing to build on.

This plan finishes the symmetry: extract the transport, then give the client a
proper `Boukensha::MCP` home that can hold more than one server.

### Where things stand

`lib/mud_manager_mcp/server.rb` is 164 lines, of which **150 (91%) are already
domain-free** — JSON-RPC framing, the initialize/initialized lifecycle, version
negotiation, error codes, notification handling. Exactly **14 lines** couple it
to the MUD:

| Line(s)  | Today                                                      | Should be                      |
| -------- | ---------------------------------------------------------- | ------------------------------ |
| 19       | `SERVER_NAME = "mud-manager"`                            | injected`name:`              |
| 122      | `serverInfo` built from that constant                    | injected`name:`/`version:` |
| 126–133 | `instructions` method returning MUD prose                | injected`instructions:`      |
| 105, 140 | `Tools.descriptors` / `Tools.call(…)` hard-referenced | injected tool provider         |
| 62       | `@registry.close_all` assumes a `SessionRegistry`      | injected`on_shutdown:`       |
| 161      | log prefix`[mud_manager.mcp]`                            | derived from`name:`          |

Same shape as the client analysis: the machinery is generic, the residue is
configuration.

---

## Status — 2026-07-24

Done and verified against the live MUD:

- **Part 1 complete.** `week1_baseline/mcp_server/` (Ruby gem) and
  `week1_baseline/python/mcp_server/` (Python port) hold the domain-free
  transport plus a `ToolTable` helper. Proven twice: an 8-line greeter server,
  and the notes server rebuilt on it (97 → 49 lines).
- **`mud_manager_mcp` consumes the framework.** Its own `server.rb` is deleted;
  what remains is `ToolProvider`, `INSTRUCTIONS`, `VERSION`. Live check:
  handshake `mud-manager v0.1.0`, `tools/list` → 31 tools, real gold/score data,
  enum errors still arrive as `isError`.
- **Part 2, Ruby half complete.** `Boukensha::MCP::{Client,Registrar,Servers}`,
  with `Tools::Mcp` as the public entry point next to `Tools::FileSystem`. Hard
  rename, no aliases — `grep McpClient` is empty.
- **Multi-server collisions.** Only names published by more than one server get
  the `server__tool` prefix; unique names stay as published. Verified by
  connecting one server twice under two keys — separate state per server, both
  `instructions` blocks in the system prompt.
- **Regression clean.** Ruby MCP 31 tools / in-process 27 tools, both resolving
  `look` to `The Temple Of Midgaard`; Python MCP 31 tools; steps 11 and 12 load.

- **Part 2, Python half complete.** `boukensha/mcp/{__init__,client,registrar,servers}.py`
  now mirror the Ruby module names (`Client`, `Error`, `ProtocolError`,
  `NAMESPACE_SEPARATOR = "__"`, `prefix`/`prefix_only`/`client` on
  `registrar.register`); `tools/mcp.py` is a thin delegator exposing `register`
  and `connect`; `mcp_client.py` deleted, `grep McpClient` empty. Verified: a
  Python-driven two-server collision test (notes server run twice) namespaces
  `note_add`/`note_list`/`notes_open`, keeps state separate (alpha holds a note,
  beta empty), folds both `instructions` blocks in, records provenance; the MUD
  path discovers `mud-manager 0.1.0` with 31 tools through the renamed client.

- **Config-driven servers complete.** A `mcp_servers:` block in `settings.yaml`
  is read by `Config#mcp_servers` (Ruby) / `Config.mcp_servers` (Python) and
  connected by `run`/`repl` through `Tools::Mcp.connect`, with per-server
  provenance recorded in the session log under `mcp_servers`. Verified in both
  languages against a config-declared notes server, and cross-language (Ruby
  agent driving the Python-built notes server twice, collisions namespaced).
  The commented schema lives in `week1_baseline/.boukensha/settings.yaml`.

  **Design note — the MUD stays a dedicated path, not folded into `mcp_servers`.**
  The plan floated `mud_mcp` becoming "shorthand for one entry". It isn't,
  deliberately: the MUD carries two things no generic entry has — an in-process
  fallback (`mud_mcp: false`, the no-Ruby path) and a REPL reachability probe —
  and those are the documented entry points steps 10–12 depend on (see
  Compatibility, and "Not in scope: removing the in-process tools"). So
  `mcp_servers:` is *additive*: it declares servers **on top of** the MUD, which
  is the config-driven capability decision 5 asked for, without regressing the
  MUD's behaviour. The MUD's tools still take part in cross-server collision
  namespacing.

- **Final verification complete.** Against the live MUD (`localhost:4000`) and
  the real mammouth/`claude-haiku-4-5` backend:
  - Regression, both languages: MCP path 31 tools, in-process path 27 tools,
    every `look` → `The Temple Of Midgaard`.
  - Live-LLM agent, both languages: `boukensha.run` with the MUD over MCP, agent
    calls `look` and reports the room correctly.
  - Steps 11_tui (0.11.0) and 12_context (0.12.0) still load.
  - Session log records `mud_tools: {source: mcp, server: mud-manager, v0.1.0}`;
    `mcp_servers` provenance uses the identical path and is `None` when none are
    declared.
  - No stale `McpClient`/`mcp_client` references in either tree; full
    `py_compile` and `ruby -c` sweeps pass.

**All parts of this plan are now done.** The MUD is one server among several,
wired the same way; a bootcamper can consume any MCP server from config or write
one on the extracted framework in Ruby or Python.

Deviation from decision 4: the separator is `__`, not `.`. Tool names accept
only `[a-zA-Z0-9_-]`; a dot is rejected by the provider API with a 400,
confirmed against a live request.

---

## Part 1 — Extract a generic MCP server

### Target API

```ruby
McpServer::Server.new(
  tools:        MudManagerMcp::Tools,     # anything answering #descriptors and #call
  name:         "mud-manager",
  version:      MudManagerMcp::VERSION,
  instructions: MudManagerMcp::INSTRUCTIONS,
  on_shutdown:  -> { registry.close_all }
).run
```

`mud_manager_mcp` becomes a *consumer* of the framework, keeping only what is
genuinely its own: `Session`, `Primitives`, `SessionRegistry`, `Tools`, and the
instructions prose.

### Where it should live

Three options; **(a) is recommended.**

- **(a) New `week1_baseline/mcp_server/`** — a small standalone gem, stdlib-only,
  mirroring the client-side split (generic piece + preset). This is the only
  option that delivers the actual goal: a bootcamper can `require "mcp_server"`
  and stand up their own server without copying code out of the MUD project.
- **(b) Keep it inside `mud_manager_mcp`, just injected** — least churn, but no
  reuse story: anyone wanting a server still has to depend on a MUD gem.
- **(c) Fold it into `boukensha`** — wrong layer. BOUKENSHA is the agent (the
  MCP *client*); shipping a server framework inside it inverts the dependency.

### Should the framework be ported per language?

**Yes — and this is the opposite call from `session.rb`, deliberately.**

`generic_interfacing.md` §2 centralised the engine because its 268 lines are
concurrency: a background reader thread, condition variables with timed waits, a
telnet IAC state machine, silence-window timing. Re-deriving that per language is
a bug farm.

The server transport has none of that. It is ~150 lines of "read a line, parse
JSON, dispatch, write a line" — no threads, no timing, no protocol state beyond a
boolean. Porting it is mechanical, and it is what lets a Python or Go bootcamper
write an MCP server in their own language. Recommend porting to Python alongside
the Ruby original, as a second reference implementation.

---

## Part 2 — `Boukensha::MCP`

### Regroup the client

| Today                                                      | Target                                                                            |
| ---------------------------------------------------------- | --------------------------------------------------------------------------------- |
| `Boukensha::McpClient` (`lib/boukensha/mcp_client.rb`) | `Boukensha::MCP::Client` (`lib/boukensha/mcp/client.rb`)                      |
| `Boukensha::Tools::Mcp` (`lib/boukensha/tools/mcp.rb`) | `Boukensha::MCP::Registrar`, with `Tools::Mcp` kept as the public entry point |
| `Boukensha::Tools::MudMcp`                               | unchanged — it is a tools preset and belongs beside`Tools::FileSystem`         |

Python mirrors this as `boukensha/mcp/{__init__,client,registrar}.py`.

The namespace is currently free (verified: no `Boukensha::MCP` anywhere), and
ten files reference the current names — a contained rename.

### The capability that is actually missing: several servers at once

Today one `register` call wires up one server. Nothing coordinates N, which is
what a real agent needs (MUD **and** Kubernetes **and** a filesystem server).
`Boukensha::MCP` should own that:

- hold several clients, close them all on exit
- concatenate each server's `instructions` into the system prompt
- **decide a tool-name collision policy** — two servers may both advertise
  `search`. Options: fail loudly, first-wins, or namespace as `server.tool`.
  Needs a decision; failing loudly is the safest default.
- surface per-server provenance in the session log, extending the `mud_tools`
  field already added into a general `mcp_servers` record

### Config-driven servers

The end state every other MCP host converges on — declare servers in
`settings.yaml` instead of in code:

```yaml
mcp_servers:
  mud:
    command: ["ruby", "…/mud_manager_mcp/bin/mud_manager_mcp"]
    env:     { MUD_NAME: dummy }
    after_connect: session_open
  kubernetes:
    command: ["kubernetes-mcp-server", "--read-only"]
    except:  ["pods_delete"]
```

`Boukensha.run` then connects to everything declared. At that point `mud_mcp:`
becomes a convenience shorthand for one entry rather than a special case.

---

## What this unlocks

- A bootcamper plugs in any third-party MCP server with **zero new code** —
  already true after the client work, but currently undocumented and unreachable
  from config.
- A bootcamper **writes** an MCP server in their own language on the framework —
  not possible today.
- The MUD stops being privileged: one server among several, wired the same way.

---

## Compatibility

Additive where possible. The `mud_mcp:` option and `Tools::MudMcp.register`
keep working unchanged — those are the documented entry points for steps 10–12.
Whether `Boukensha::McpClient` survives as an alias to `MCP::Client` is a
decision below.

Ruby steps **11_tui** and **12_context** must be checked again: the last rename
showed they carry byte-identical copies of `tools/mud.rb` and their own gemspec
dependency. They do not use the MCP client today, but any gem-name change
reaches them.

---

## Verification

1. Rebuild the notes server (`scratchpad/notes_mcp_server.py`) **on the extracted
   framework**. If the framework is genuinely generic, an unrelated server should
   need nothing but its tool table and instructions — that is the server-side
   equivalent of the client-side proof already done.
2. Drive two servers simultaneously from one agent (MUD + notes), including a
   deliberate tool-name collision, and confirm the chosen policy fires.
3. Full MUD regression: 31 tools over MCP, 27 in-process, 0 with `mud: false`;
   `look`/`check` against the live server on both paths.
4. Live LLM agent in both languages, unchanged behaviour.
5. Steps 11 and 12 still load.
6. Session log records per-server provenance.

---

## Decisions needed before starting

1. **Where the generic server lives** — recommend (a), a new `mcp_server` gem.
  - new mcp_server
2. **Port the server framework to Python too?** Recommended yes; unlike
   `session.rb` there is no concurrency risk, and it is what lets non-Ruby
   bootcampers write servers.
   - yes, to python too
3. **Namespace migration** — hard rename, or keep `Boukensha::McpClient` as a
   deprecated alias?
   - hard renaming 
4. **Tool-name collision policy** across servers — fail loudly / first-wins /
   `server.tool` prefixing.
   - yes, `server.tool` prefixing
5. **Is `settings.yaml`-driven server declaration in scope now**, or a follow-up
   once the namespace exists?
   yes, is in scope

## Not in scope

- The backends' `required`-for-every-parameter behaviour (worked around by
  pruning in `Tools::Mcp`; fixing it properly touches 6 backend files per
  language and changes the existing lesson tools).
- Removing the in-process `tools/mud.*` and `python/mud_manager/` — kept
  deliberately as the no-Ruby fallback and as the side-by-side comparison that
  makes the MCP argument legible.
- MCP features beyond tools (resources, prompts, sampling). Worth a later look;
  nothing in the bootcamp needs them yet.
