Our MudManager is written in Ruby.
In our Bootcamp, Bootcampers want to ouse their own langauge eg. Java, Python, Rust, Go.
What is the solution?

- We have to create wrapper per lang
- We make MudManager a command line tool, and other langs execute shell commands in
  their langs
- We implement a communication protcol
- We implement MCP as a layer.

## Technical Exploration

### 1. The one constraint that decides everything

The MUD session is **stateful, long-lived, and receives data between our calls.**
Measured against the live tbaMUD server on `localhost:4000`:

| Operation | Cost |
|---|---|
| TCP connect | 2 ms |
| Login dance (name → password → menu → enter world) | 5,911 ms |
| **connect + login total** | **5,913 ms** |
| Command roundtrip on an already-open session | ~97 ms (89.9 / 100.0 / 100.0) |

**A command on a cold session costs ~61× a command on a warm one.** Login is
99.96% of that cost.

Second measurement — data arrives while the client does nothing. Sent `help`,
then deliberately read nothing for 3 seconds, then drained: **1,375 characters
were already buffered.** A process that exits between commands loses exactly
this data.

On top of the socket, the *game* is stateful too: room position, combat state,
hunger/thirst ticks, and CircleMUD's "already playing → reconnect?" prompt
(already noted as unhandled in the Ruby README's Technical Considerations).
Re-logging per command would hit that prompt every time.

> **Therefore: every viable solution must keep one long-lived process holding
> the socket.** This single fact eliminates one of the four options outright
> and reshapes the other three.

### 2. Where the complexity actually sits

The 691 LOC do not split evenly by risk:

| File | LOC | Nature | Port risk |
|---|---|---|---|
| `primitives.rb` | 418 | 58 pure functions: string building + enum validation. No I/O, no concurrency, no timing. | **Low** — mechanical translation |
| `session.rb` | 268 | Background reader thread, mutex + condition variable with timed waits, telnet IAC byte-level state machine, silence-window timing on a monotonic clock, login regex sequencing. | **High** |

**The big file is the easy one; all the risk lives in the small one.**

This is not speculation — `week1_baseline/python/mud_manager/` is a completed
port (751 LOC). `primitives.py` was a mechanical rewrite. `session.py` required
genuinely re-deriving the concurrency: `threading.Condition` in place of Ruby's
`Mutex`/`ConditionVariable`, `time.monotonic()` timing, and byte-level IAC
handling (Ruby strings are byte-oriented, Python's are not — a real source of
divergence).

That split is the lever for the whole decision: **centralize `session.rb` and
you remove nearly all porting risk**, while `primitives.rb` stays cheap to
duplicate — or can be served centrally too.

### 3. The four options against those facts

#### Option B — CLI tool + shell out: **not viable as stated**

A one-shot CLI process must connect+login per invocation. That means ~6 s
latency and 61× overhead per command, it discards game state, it loses async
output buffered between calls, and it trips the reconnect prompt on every run.

It *is* rescuable as a **daemon** (`mud_manager serve` holding the session,
short-lived commands talking to it) — but that is Option C wearing a CLI
costume, not a separate design.

#### Option A — port per language: works, proven, but N× the risk

- **For:** no runtime dependency, no IPC, idiomatic in each language, debuggable
  in-language, bootcamper owns the whole stack.
- **Against:** `session.rb`'s concurrency must be re-derived per language across
  genuinely different threading models — Go goroutines/channels, Rust
  ownership/async, Java threads, Python's GIL. The silence-window algorithm is
  timing-sensitive and a likely bug farm. Every `primitives` change multiplies
  by N languages.

Proven feasible (the Python port works), but that is 1 of 4 languages, and the
risky 273 lines needed re-derivation rather than translation.

#### Option C — communication protocol: fits the constraint directly

One daemon owns the session; each language ships a thin RPC stub instead of a
full port.

Transport matters less than it first appears — the same JSON message schema
works over stdio, TCP, or HTTP. **Line-delimited JSON over a subprocess's
stdin/stdout** is the lowest-friction default: every target language can spawn
a process and read/write lines with zero third-party dependencies, in well
under 100 lines.

**Critical API design point:** because the MUD pushes data, the protocol must
expose the *read* primitives — `drain`, `read_until_quiet`, `read_until_prompt`
— as first-class calls, not merely "send command → get response". The existing
Ruby API already models this correctly; preserve that shape rather than
flattening it into request/response.

#### Option D — MCP: a layer *on top of* C, not an alternative to it

MCP is JSON-RPC 2.0 plus a tool-discovery/tool-call schema over stdio or HTTP.
Build Option C and you are most of the way to MCP already.

- **For:** the end consumer here *is* an LLM agent, so MCP matches the real use
  case; tool descriptions travel with the protocol; client ecosystem exists.
- **Against as the primary interface:** MCP semantics are LLM tool calls. A Rust
  program that wants `look()` would pull in an MCP client library for what
  should be one RPC. Client maturity outside Python/TS is younger. And there is
  **no MCP anywhere in this repo today** — it would be entirely net-new surface.

### 4. The question to settle before choosing a transport

This fork is pedagogical, not technical, and it changes the answer:

- If bootcampers are meant to **learn to build the agent's tool layer**, then
  handing them ready-made MCP tools deletes the Step 10 lesson
  (`10_standard_tool_library` is precisely about writing tool modules).
- If the MUD is **incidental plumbing** and the lesson is agent architecture,
  then abstract it away as aggressively as possible.

### 5. Recommendation — hybrid, staged

1. **Extract `session.rb` behind a daemon** speaking line-delimited JSON over
   stdio, with an optional TCP mode. This removes nearly all porting risk while
   leaving the cheap part cheap.
2. **Ship it containerized.** The repo already runs the MUD itself as a
   container exposing TCP 4000 (`week0_explore/infrastructure/`), so this
   matches existing norms — and it removes the "must install Ruby" objection for
   Java/Go/Rust bootcampers entirely.
3. **Keep `primitives` optional per language.** Mechanical, low-risk, and it
   teaches the command surface. Serve it from the daemon instead if you would
   rather bootcampers not touch it.
4. **Add MCP as a second adapter over the same core** if and when LLM agents
   should consume it directly — an adapter, not a rewrite.

### 6. What this exploration did *not* establish

- **Async chatter under load.** A 25-second idle listen saw 0 unsolicited
  messages — but the server was quiet and the character was standing safely in
  the Temple of Midgaard. That does *not* prove chatter is rare: combat rounds,
  wandering mobs, other players' channels, and hunger/thirst ticks all push
  unprompted. Combat was not induced (it risks the character). The library's own
  docstring states async chatter is expected — **design for push regardless.**
- **Multi-client semantics.** `drain` is destructive. If two clients share one
  daemon session, one silently steals the other's buffer. Needs an explicit
  decision: single-client sessions, or per-client read cursors.

---

## 7. Implementation

Built as recommended: MCP over stdio. Then refactored — see §8 — so the MCP
server *is* the deliverable rather than a layer bolted onto a separate gem.

### What was added

| Component | Where | LOC |
|---|---|---|
| MCP server (JSON-RPC 2.0 / stdio, protocol `2025-06-18`) | `mud_manager/lib/mud_manager/mcp/server.rb` | 166 |
| Session registry (multi-session) | `…/mcp/session_registry.rb` | 112 |
| Declarative tool table (31 tools) | `…/mcp/tools.rb` | 461 |
| Executable | `mud_manager/bin/mud_manager_mcp` | 73 |
| Ruby MCP client | `ruby/10_standard_tool_library/lib/boukensha/mcp_client.rb` | 157 |
| Ruby adapter | `…/lib/boukensha/tools/mud_mcp.rb` | 120 |
| Python MCP client | `python/10_standard_tool_library/boukensha/mcp_client.py` | 204 |
| Python adapter | `…/boukensha/tools/mud_mcp.py` | 151 |

Hand-rolled rather than using the `mcp` gem / PyPI package, so `mud_manager`
keeps its zero-dependency gemspec and the wire protocol stays readable.

Opt-in and non-breaking: `Boukensha.run(mud_mcp: true)` / `run(mud_mcp=True)`.
Default stays `false`, so the in-process path is untouched (verified: still
registers 27 tools and works).

### The payoff, measured

Cost of giving one more language the same MUD tool set:

| | Ruby | Python |
|---|---|---|
| In-process (`tools/mud.*`) — tool definitions restated per language | 480 | 556 |
| Via MCP (`tools/mud_mcp.*`) — **zero** tool definitions | **120** | **151** |

The adapters contain no tool names, descriptions or schemas at all; they call
`tools/list` and register whatever comes back. Their size is therefore
independent of the tool count — a 32nd tool costs 0 lines in every client, in
every language. (`mcp_client.*` is generic MCP plumbing, reusable against any
MCP server, not MUD-specific.)

This confirms the framing in §"Does mud_manager_mcp replace mud_manager?": it
does not. `mud_manager` (686 LOC of socket, thread, IAC and login handling)
stays exactly as it was — MCP cannot speak telnet. What MCP removes is the
*per-language duplication of the tool layer* on top of it.

### Multi-session

Every tool takes an optional `session_id` (default `"default"`); the registry
holds one `MudManager::Session` per id behind a mutex, and `close_all` runs on
stdin EOF, SIGINT and SIGTERM so characters are not left linkdead.

Verified concurrently — the real MUD plus a second endpoint, in one server
process: routing is correct (`send_raw` to the second session returned that
server's tagged reply while `check` returned real game data), buffers stay
independent, and closing one session leaves the other working.

A second endpoint was needed because the MUD has exactly one character whose
password we hold, and CircleMUD hands the connection over ("Reconnecting") if
the same character logs in twice — so two sessions on one character would have
tested nothing. Documented as a real constraint: multi-session means multiple
*characters*.

### Verified end-to-end

- Raw JSON-RPC: handshake, `tools/list` (31 tools), `tools/call`, notification
  handling, unknown-tool and unknown-session error paths.
- Both clients against the live tbaMUD: tool discovery, `look`, `check`, and
  enum-validation errors surfacing as agent-correctable `isError` text.
- **A real LLM agent (mammouth / claude-haiku-4-5) playing through MCP in both
  languages**, against the same Ruby server — each correctly reported the Temple
  of Midgaard and level 3, matching actual game state.

### Known rough edge

BOUKENSHA's backends mark *every* declared parameter as required
(`to_tools`: `required: tool.parameters.keys`), but MCP schemas have genuinely
optional fields — `session_id` everywhere, and `look` takes none at all. The
model therefore fills optionals with `""` to satisfy the schema.

Worked around in both adapters by pruning nil/blank arguments before the call,
so `look(target: "")` behaves as `look`. Verified. The cleaner fix — honouring
optionality in `to_tools` — was deliberately not taken: it would touch 6 backend
files per language and change behaviour for the existing lesson tools, which is
out of scope for an additive change.

---

## 8. Refactor: the library *becomes* the MCP server

§7 shipped MCP as an optional layer over a `mud_manager` gem, and argued the two
were separate concerns. That framing was rejected in favour of a single
deliverable: **`mud_manager_mcp`**. The engine did not disappear — it moved
inside.

### Renamed

| Before | After |
|---|---|
| `week1_baseline/mud_manager/` | `week1_baseline/mud_manager_mcp/` |
| gem `mud_manager` | gem `mud_manager_mcp` (ships the `mud_manager_mcp` executable) |
| `MudManager::Session` / `::Primitives` | `MudManagerMcp::Session` / `::Primitives` |
| `MudManager::MCP::Server` / `::SessionRegistry` / `::Tools` | `MudManagerMcp::Server` / `::SessionRegistry` / `::Tools` |

The inner `MCP` namespace was flattened: `MudManagerMcp::MCP::Server` is
redundant once the whole gem is the server. `lib/mud_manager_mcp/mcp/` is gone
and its three files sit directly under `lib/mud_manager_mcp/`.

### Blast radius beyond step 10

Ruby steps **11_tui** and **12_context** also depend on the gem and use
`MudManager::` in their own `tools/mud.rb` (byte-identical to step 10's). Both
gemspecs and all three `tools/mud.rb` were updated, `Gemfile.lock`s
re-resolved, and both steps verified to still load. Missing this would have
broken two later lessons.

### MCP is now the default

`mud_mcp` flipped from `false` to `true` in `run`/`repl` in both languages, and
the registration logic was restructured:

- `mud: false` → no MUD tools at all, whatever `mud_mcp` says
- a Hash/dict in `mud:` is a connection override, else config supplies it
- **no connection settings anywhere → no MUD tools and no server process.**
  Without this guard, every `run()` in a project with no MUD configured would
  have spawned a Ruby subprocess and failed.

`mud_mcp: false` still selects the in-process `Tools::Mud`, kept deliberately:
it is the pure-Python path that needs no Ruby on PATH, and it is the side-by-side
comparison that makes the MCP argument legible (27 hand-written tools vs. 31
discovered ones).

### Verified after the refactor

- Syntax/compile clean across both languages; no `MudManager` reference without
  `Mcp` survives anywhere in live code.
- Gem rebuilds, installs, and puts `mud_manager_mcp` on `PATH`; the executable
  answers a raw `initialize` correctly.
- Standalone examples in both languages still run against the live MUD.
- **Steps 11 and 12 still load** with `MudManagerMcp::Session` resolving.
- Step 10, both languages, all three paths: MCP default → 31 tools incl.
  `session_open`; `mud_mcp=false` → 27 tools incl. `mud_connect`; `mud=false`
  → 0 tools and no subprocess. `look` returns the real room on both paths.
- **Live LLM agent in both languages with no flag at all**, now going through
  MCP by default — each correctly reported level 3 in the Temple of Midgaard.

### Consequence worth noting

With MCP as the default, Python step 10 needs **Ruby on PATH** for MUD play.
That is inherent to centralising the engine in one language, and is the reason
`tools/mud.py` and `python/mud_manager/` were kept rather than deleted:
`mud_mcp=False` remains a fully self-contained Python path.
