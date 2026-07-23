# Plan: Port `ruby/10_standard_tool_library` → `python/10_standard_tool_library`

Status: **implemented**
Date: 2026-07-23

## Scope

1. Port the Ruby `10_standard_tool_library` step into
   `week1_baseline/python/10_standard_tool_library`.
2. Vendor a Python port of the `mud_manager` gem (source at
   `week0_explore/mud_manager/`) at **`week1_baseline/python/mud_manager/`** —
   a sibling of every step directory, not nested inside step 10 — since no
   PyPI package provides CircleMUD session management.
3. Add two launcher scripts:
   - `week1_baseline/bin/10_standard_tool_library_ruby`
   - `week1_baseline/bin/10_standard_tool_library_python`

## Strategy

Copy `python/09_global_executable` as the baseline, then apply the Ruby
`09 → 10` deltas. This is the first step where the agent gets real
capabilities instead of pure chat: a `FileSystem` tool module (sandboxed file
I/O), a `Shell` tool module (sandboxed command execution), and a `Mud` tool
module (CircleMUD gameplay). `working_dir:`/`allowed_commands:`/
`shell_timeout:`/`mud:` become new keyword args on `Boukensha.run`/`repl`.

What step 10 adds/changes (from the Ruby `09 → 10` diff):
- New `lib/boukensha/tools/file_system.rb`, `shell.rb`, `mud.rb`.
- `boukensha.rb`: new kwargs `working_dir:` (default `Dir.pwd`),
  `allowed_commands:` (default `nil` = allow all), `shell_timeout:` (default
  `30`), `mud:` (default `nil` = read from config); auto-registers
  `FileSystem`+`Shell` when `working_dir` is truthy, auto-registers `Mud` when
  MUD options resolve (explicit `mud:` hash, or `mud_opts_from_config` reading
  `settings.yaml`'s `mud:` block if `mud_host`+`mud_username` are set); `mud:
  false` / `working_dir: false` opt out.
- `context.rb`: `Context` gains a `working_dir` attribute (expanded to an
  absolute path).
- `repl.rb`: banner gains an API-key-set indicator, a config-dir-exists check,
  and a `mud:` status line (TCP-reachability probe only — no login, to avoid
  double-login since the tool session auto-connects at registration).
- `boukensha_loader.rb`: legacy `MUD_NAME`/`MUD_HOST`/`MUD_PORT`/
  `MUD_PASSWORD` env vars still work and take precedence over config.
- `boukensha.gemspec`: new runtime dependency `mud_manager (~> 0.1)`.
- `version.rb`: `0.9.0` → `0.10.0`.
- New `examples/example.rb` (MUD demo).
- Config layer (`config.rb`) is **unchanged** — `mud_host`/`mud_port`/
  `mud_username`/`mud_password` already existed there before step 10 (and the
  Python `config.py` already has them ported since `09`), so no config work is
  needed on either side.

## `mud_manager` port

Source: `week0_explore/mud_manager/lib/mud_manager/{session.rb,primitives.rb}`
— pure stdlib (`socket` + `thread`), no external deps, so the Python vendor
needs no new dependencies either (`socket` + `threading` + `re` + `time`).

New top-level package **`python/mud_manager/`** (sibling of every step
directory, mirroring Ruby's `mud_manager` being its own gem rather than
duplicated per step). `boukensha/tools/mud.py` adds `python/` onto
`sys.path` (via `Path(__file__).resolve().parents[3]`) before importing it,
the same way `boukensha_loader.py` resolves a step directory onto
`sys.path` — no install step needed.

- `session.py` — port of `session.rb`'s `Session` class: `socket.socket`
  connection, a background daemon `threading.Thread` draining the socket into
  a buffer guarded by a `threading.Condition`, telnet IAC-sequence stripping,
  `send_command`, `drain`, `read_until_quiet`, `read_until` (regex-based),
  the `read_until_prompt` sentinel (`"> "`), and the `login()` CircleMUD
  dance. Exception hierarchy: `SessionError`, `ConnectionError`, `LoginError`,
  `MudTimeoutError` (named to avoid shadowing the builtin `TimeoutError`).
- `primitives.py` — port of `primitives.rb`: stateless command-builder
  functions returning a `Command` dataclass (`primitive`, `raw`, `verb`,
  `args`), the same enum tables (`DIRECTIONS`, `POSITIONS`, `ATTACK_STYLES`,
  …) and the same `check_enum!`/`require_str!` validation helpers (raising
  `ValueError` in place of Ruby's `ArgumentError`).

## New files

1. **`python/mud_manager/__init__.py`, `session.py`, `primitives.py`** —
   vendored port, as described above (top-level, sibling of the step dirs).

2. **`boukensha/tools/__init__.py`** — package marker, re-exports
   `FileSystem`/`Shell`/`Mud` submodules for `Tools.FileSystem.register(...)`-
   style access.

3. **`boukensha/tools/file_system.py`** — port of `tools/file_system.rb`:
   `register(registry, *, working_dir)` registering `pwd`, `list_directory`,
   `read_file`, `write_file`, `delete_file`, `search_files`, using the
   existing decorator-based `registry.tool(...)` idiom (see
   `boukensha/run_dsl.py`), not Ruby's trailing block. Path containment via
   `Path.resolve()` + `is_relative_to()` (Python `>= 3.11`, already the
   `pyproject.toml` floor); returns an `"error: ..."` string instead of
   raising on traversal, exactly like Ruby. `search_files` uses `re` +
   `Path.rglob(glob)`.

4. **`boukensha/tools/shell.py`** — port of `tools/shell.rb`:
   `register(registry, *, working_dir, timeout=30, allowed_commands=None)`
   registering `run_command`, using `subprocess.run(..., shell=True,
   cwd=working_dir, timeout=timeout, capture_output=True)` in place of
   `Open3.capture2e` + `Timeout.timeout`, catching
   `subprocess.TimeoutExpired`/`OSError`. Same allow-list guard (check the
   first whitespace-split token before executing).

5. **`boukensha/tools/mud.py`** — port of `tools/mud.rb`:
   `register(registry, *, host="localhost", port=4000, name, password)`,
   building one shared `mud_manager.Session` via closure, registering the
   same ~25 tools grouped identically (Connection / Perception / Movement /
   Combat / Communication / Inventory & equipment / Magic / Utility), each
   wrapping a `Primitives` call and catching `ValueError` the way Ruby
   catches `ArgumentError`. Auto-connects at registration time (best effort;
   warns to stderr on failure rather than raising, matching Ruby).

6. **`examples/example.py`** — port of Ruby's `examples/example.rb` MUD demo:
   load config, call `boukensha.run(task=..., working_dir=False)`, letting
   MUD config come from `settings.yaml`.

## Modified files (mirroring the Ruby `09 → 10` deltas)

7. **`boukensha/version.py`** — `VERSION = "0.10.0"`.

8. **`boukensha/context.py`** — add a `working_dir` attribute to
   `Context.__init__` (expanded/resolved to an absolute `Path` when given,
   else `None`).

9. **`boukensha/__init__.py`** — `run()`/`repl()` gain kwargs:
   `working_dir: str | Path | bool = True`, `allowed_commands: list[str] |
   None = None`, `shell_timeout: int = 30`, `mud: dict | bool | None = None`.
   `working_dir` uses a tri-state `True`/`False`/path form rather than a
   `Path.cwd()` default value — a mutable default expression is evaluated
   once at function-definition time in Python, not per call like Ruby's
   `Dir.pwd` default, so `_resolve_working_dir()` computes `Path.cwd()`
   inside the function body instead. When resolved truthy, auto-register
   `Tools.FileSystem`+`Tools.Shell`. Resolve MUD options via
   `_resolve_mud(mud, cfg)` + a private `_mud_opts_from_config(cfg)` helper
   (mirrors Ruby's `mud_opts_from_config`): `mud is False` → skip; not `None`
   → use as-is; `None` → build from `config()`, returning `None` unless both
   `mud_host` and `mud_username` are set. Register `Tools.Mud` only if
   resolved. Pass the resolved mud dict through to `Repl(...)` for the
   banner.

10. **`boukensha/repl.py`** — `Repl.__init__` gains a `mud` kwarg;
    `_banner()` gains an API-key-set indicator (`✓`/`✗`), a config-dir-exists
    check, and a new `mud:` line via `_mud_status_string()`/`_probe_mud(host,
    port, name, password)` — TCP-reachability-only probe via
    `socket.create_connection(..., timeout=3)` (no login, to avoid a double
    login since the tool session already auto-connects at registration).

11. **`boukensha_loader.py`** — update the step-number docstring to step 10;
    add the legacy `MUD_NAME`/`MUD_HOST`/`MUD_PORT`/`MUD_PASSWORD` env-var
    override: if `MUD_NAME` is set, call `boukensha.repl(working_dir=False,
    mud={...})`; otherwise call `boukensha.repl()` unmodified so
    `_mud_opts_from_config` reads `settings.yaml`.

12. **`pyproject.toml`** — `version = "0.10.0"`, `description` updated to
    mention the standard tool library. No new `[project.dependencies]` —
    everything used (`socket`, `threading`, `subprocess`, `re`) is stdlib.

13. **`README.md`** — rewrite as the Step 10 port doc, following the existing
    Python-port convention (pointer to the Ruby README for full rationale;
    Python specifics: the `tools/` package layout, the decorator-based
    `registry.tool` usage example, and a note that `mud_manager` is vendored
    rather than pip-installed because no PyPI equivalent exists).

14. **`prompts/system.md`, `py.typed`** — carry forward unchanged (Ruby step
    10 doesn't touch `system.md`).

### Bug fix discovered during verification (not a Ruby→Python delta)

**`boukensha/client.py`** — `Client.call()` now filters out any header whose
value is `None` before calling `connection.request(...)`. Root cause: with no
API key configured, `backends/anthropic.py`'s `headers()` puts `None` into
`x-api-key`; Python's `http.client.putheader()` raises a raw `TypeError` for a
`None` header value, crashing before the request is even sent. Ruby's
`Net::HTTP` tolerates a `nil` header value and lets the request go out, so the
*server* returns a clean 401 (`"x-api-key header is required"`), which the
existing retry/`ApiError` handling already surfaces as a normal error message.
This bug is inherited unchanged from step 09's `client.py` (not introduced by
this port) and is very likely present in Python steps 05–09 too, since none of
them touch this code path — not fixed there as part of this plan; flagged to
the user as a candidate backport.

## bin scripts

15. **`bin/10_standard_tool_library_ruby`** — unlike step 09, the gemspec now
    declares a runtime dependency on `mud_manager (~> 0.1)`, which is not a
    published gem — it's vendored at `week0_explore/mud_manager/`. Confirmed
    working approach: `gem install --local
    week0_explore/mud_manager/mud_manager-0.1.0.gem` (idempotent, guarded by
    `gem list -i`) makes the gem resolvable to the system gem index, after
    which a plain `bundle install && bundle exec ruby bin/boukensha` resolves
    and runs with no network access needed beyond the first-time bundler
    self-install.

16. **`bin/10_standard_tool_library_python`** — same shared-venv bootstrap
    pattern as `09_global_executable_python` (`python-dotenv`, `PyYAML`; no
    new deps needed since `mud_manager` is vendored, not pip-installed), then
    `exec .venv/bin/python 10_standard_tool_library/bin/boukensha`.

Both scripts `chmod +x`.

### Addendum: `mud_manager`-only launcher scripts (requested separately)

Two more launchers were added on request, to run `mud_manager` standalone
(no `boukensha` agent involved) — a minimal connect/login/`look`/close demo:

- **`bin/mud_manager_ruby`** — `cd week0_explore/mud_manager && exec ruby
  examples/simple.rb`. No `gem install`/bundler needed: the example loads the
  library via `require_relative`, not as an installed gem.
- **`bin/mud_manager_python`** — `cd python && exec python3
  mud_manager/examples/simple.py`. No venv/pip needed (pure stdlib). Required
  writing `python/mud_manager/examples/simple.py` first, a port of Ruby's
  `mud_manager/examples/simple.rb` that didn't have a Python equivalent yet.

Both verified live against the real CircleMUD server at `localhost:4000`,
output byte-for-byte equivalent between the two languages.

## Verification — results

17. **Byte-compile**: `python -m compileall 10_standard_tool_library` +
    `mud_manager/*.py` — clean, no syntax errors. ✅
18. **`FileSystem`/`Shell` round-trip** against a throwaway `Registry` +
    temp dir: `pwd`/`write_file`/`read_file`/`list_directory`/
    `search_files`/`delete_file` all behaved as expected; `read_file` on
    `../../etc/passwd` returned `"error: path '../../etc/passwd' escapes the
    working directory"` without touching the real filesystem;
    `run_command` with `allowed_commands=["python3"]` ran `python3 -c
    "print(1+1)"` (→ `"2"`) and rejected `ls -la` (→ `"error: 'ls' is not in
    the allowed-commands list (python3)"`); a sleeping subprocess exceeding
    the default timeout was killed. ✅
19. **`primitives.py` smoke check**: `move("north")`, `attack("kill",
    "goblin")`, `look()`, `look(target="sword", preposition="at")`,
    `equip("wear", "ring", body_loc="finger")` all produced the same `.raw`
    strings as the Ruby original; `move("sideways")` raised
    `ValueError: invalid direction: 'sideways' (expected one of north, east,
    south, west, up, down)`. ✅
20. **`mud_manager.Session` against a real CircleMUD server** — this
    environment has one running at `localhost:4000` with credentials in
    `~/.boukensha/settings.yaml`, so this went beyond the planned offline-only
    check: connecting to a closed port (`127.0.0.1:1`) raised
    `ConnectionError: connect 127.0.0.1:1 failed: [Errno 111] Connection
    refused`; `Repl._probe_mud` returned `"✗ not reachable"` for the closed
    port and `"(Reachable)"` for the live server. Full live round-trip via
    `Tools.Mud.register(...)` (auto-connect + login) then `mud_status` →
    `"connected to localhost:4000"`, `look` → the actual Temple of Midgaard
    room description, `check(kind="score")` → real character stats,
    `mud_disconnect` → `"disconnected"`. ✅
21. **REPL banner smoke** via `bin/10_standard_tool_library_python` (piped
    `/exit`): renders `v0.10.0`, `config: /home/…/.boukensha`, `provider:
    anthropic (claude-haiku-4-5)  ✗ API key not set`, `mud:  localhost:4000
    (Reachable)` — matches `bin/10_standard_tool_library_ruby`'s output
    (also run and confirmed identical layout/values) side by side. ✅
22. **Live agent round-trip with `working_dir` tools** via local Ollama
    models: `boukensha.run(..., backend="ollama", working_dir=<temp dir>,
    mud=False)` with a task asking the agent to list files and read a
    planted `note.txt`, to confirm the `run()`/`repl()` auto-registration
    wiring (not just direct `Tools.X.register()` calls) end-to-end through a
    real tool-calling LLM loop.
    - `gemma3:12b` — rejected immediately by the Ollama server itself with a
      clean `ApiError`: `400 {"error":"...gemma3:12b does not support
      tools"}`. Not a bug — this model has no tool-calling capability
      (confirmed via `/api/tags`: `"capabilities": ["completion"]`, no
      `"tools"`), and this also incidentally verified the non-2xx-status
      error path end-to-end.
    - `gpt-oss:20b` (the only local model with `"tools"` capability) — too
      slow for a full round trip on this CPU-only host within a patient
      wait; the user independently hit the same wall via the Ruby launcher
      (`Net::ReadTimeout` after 4 attempts, ~4 minutes). Abandoned as a
      verification path by user decision — the environment's compute, not
      the port, is the limiting factor. Full tool-registration wiring
      through `run()`/`repl()` (as opposed to direct `Tools.X.register()`
      calls, already verified in #18/#20) remains unverified through an
      actual LLM loop, though every non-LLM layer of that path (resolve
      helpers in #23, direct tool dispatch in #18/#20) is covered.
23. **Resolve-helper checks**: `_resolve_working_dir(True)` → `Path.cwd()` at
    call time; `_resolve_working_dir(False)` → `None`; `_resolve_working_dir("/tmp")`
    → `Path("/tmp")`. `_resolve_mud(None, cfg)` → built from
    `settings.yaml`'s `mud:` block; `_resolve_mud(False, cfg)` → `None`;
    `_resolve_mud({...}, cfg)` → the explicit dict, unmodified. ✅
