# Plan: Port `ruby/04_api_client` to Python

## Goal

Port `week1_baseline/ruby/04_api_client` into `week1_baseline/python/04_api_client/` (directory
doesn't exist yet). This step adds the **API Client** — `Client`, which takes the payload
assembled by `PromptBuilder`, POSTs it to the backend's URL over plain HTTP (no third-party HTTP
library, by explicit design — see below), retries on transient network errors and retryable
status codes with exponential backoff, and returns the parsed JSON response. One HTTP round
trip, no tool-calling loop yet (that's step 5). It carries forward every convention established
in `00_config` through `03_prompt_builder` (see those four plans/READMEs) — this plan only calls
out what's new or different for step 4.

## Reference files (what to port from)

| Ruby file                                                          | Role                                                                                                   |
| ---------------------------------------------------------------------| ---------------------------------------------------------------------------------------------------------|
| `week1_baseline/ruby/04_api_client/README.md`                      | Spec — `Client` API table, retry/SSL considerations, sample raw responses per backend                    |
| `week1_baseline/ruby/04_api_client/lib/boukensha/client.rb`        | New — `Client`: builds the request, retries transient errors/retryable statuses with backoff, raises `ApiError` on final failure, returns parsed JSON |
| `week1_baseline/ruby/04_api_client/lib/boukensha/errors.rb`        | Adds `ApiError` alongside step 3's `UnknownToolError`/`UnsupportedModelError`                             |
| `week1_baseline/ruby/04_api_client/lib/boukensha/config.rb`        | Same as step 3 except `PROMPTS_DIR`'s relative path grew one `../` too many — **likely an unintentional bug**, see below |
| `week1_baseline/ruby/04_api_client/lib/boukensha/tasks/base.rb`    | Two small changes from step 3: error-message text `settings.yml`→`settings.yaml`, and a new `fetch` guard (`return nil unless settings.is_a?(Hash)`) |
| `week1_baseline/ruby/04_api_client/prompts/system.md`              | New text for this step (different persona copy than step 3's)                                             |
| `week1_baseline/ruby/04_api_client/lib/boukensha.rb`                | Top-level require wiring — adds `boukensha/client`, drops the now-redundant standalone `backends/base` require (each backend already requires it) |
| `week1_baseline/ruby/04_api_client/examples/example.rb`            | Runnable example — registers `read_file`/`list_directory` tools, builds a backend from `settings.yaml`, sends one real HTTP request via `Client#call`, pretty-prints the raw JSON response |
| `week1_baseline/ruby/04_api_client/lib/boukensha/{tool,message,context,registry,prompt_builder}.rb` and `lib/boukensha/backends/*.rb` and `lib/boukensha/tasks/player.rb` | **Byte-identical to step 3** (confirmed via `diff -rq` against `ruby/03_prompt_builder/lib`) |
| `week1_baseline/python/03_prompt_builder/boukensha/{tool,message,context,registry,prompt_builder}.py` and `boukensha/backends/*.py` and `boukensha/tasks/player.py` | Source to copy the unchanged files from directly |

## What's different from step 3 (read before porting)

- **New `Client` class — this step's centerpiece.** Builds one `POST` request from
  `builder.url`/`builder.headers`/`builder.to_api_payload(...)`, with:
  - `RETRYABLE_STATUS_CODES = {408, 409, 429, 500, 502, 503, 504}`
  - `TRANSIENT_ERRORS` — a list of network-level exception classes to retry on (connection
    reset/refused, open/read timeout, SSL error, socket/DNS error, unexpected EOF)
  - `MAX_RETRIES = 3`, `BASE_RETRY_DELAY = 0.5` (seconds), exponential backoff
    `delay(attempt) = BASE_RETRY_DELAY * 2 ** (attempt - 1)`
  - Exact retry semantics (verified by tracing the Ruby loop): **up to 4 total attempts** before
    giving up, whether failures come from transient exceptions or retryable status codes — sleeps
    happen only before attempts 2, 3, and 4 (delays 0.5s, 1.0s, 2.0s), never after the 4th
    attempt. On final failure: a transient exception on attempt 4 raises `ApiError` with the
    underlying exception's class/message; a persistent retryable (or any non-2xx) status raises
    `ApiError` with the status code and response body.
  - Ruby's `README.md` states explicitly: **"No Dependencies" — `Client` uses Ruby's standard
    `net/http`, no gems, "to keep things explainable"; this is intentional, not an oversight.**
    The Python port must honor the same constraint: **stdlib HTTP only — no `requests`/`httpx`.**
- **`errors.rb` gains `ApiError`** — raised by `Client#call` on final failure (after retries are
  exhausted).
- **`config.rb`'s `PROMPTS_DIR` calculation looks broken.** Diffing against step 3's
  byte-identical `config.rb`, the only change is `File.expand_path("../../prompts", __dir__)` →
  `File.expand_path("../../../prompts", __dir__)` — one extra `../`. Both files live at the same
  relative depth (`lib/boukensha/config.rb`), so the extra `../` walks one directory too far.
  Verified directly: it resolves to `week1_baseline/ruby/prompts` (outside `04_api_client/`
  entirely), which **does not exist** — confirmed with `File.exist?` returning `false`. Practical
  effect: `Tasks::Player.system_prompt` silently falls back to `nil` for the shipped default
  prompt unless the user has their own `.boukensha/prompts/player/system.md` override (this
  doesn't crash — `read_default_prompt` just returns `nil` for a missing file — so the bug is
  silent, matching the "AI-driven edits regressed some docs/code" pattern `ITERATIONS.md`
  self-reports elsewhere in this project). Unlike the doc-only drift flagged in earlier steps'
  plans, or step 3's latent/unreachable `PromptBuilder` arity bug, **this one has a real, visible
  functional consequence for anyone running the step with default settings** — flagged as an
  open question below since it's arguably too consequential to port faithfully without asking.
- **`tasks/base.rb`: two small, unambiguous changes** (not open questions — port directly):
  1. Error-message text fix, `settings.yml` → `settings.yaml` (matches the actual file name).
  2. `fetch` gains a defensive guard, `return nil unless settings.is_a?(Hash)`, so passing a
     non-dict `settings` (e.g. `None`, from `Config.tasks("unknown_task")`) degrades to the
     existing "provider/model is required" `ArgumentError` instead of crashing with a raw
     `NoMethodError`/`AttributeError` deeper in the call chain.
- **New `prompts/system.md` text** for this step (different persona copy from step 3's) — ship
  verbatim, same pattern as prior steps' per-step prompt text.
- **This step performs real I/O** — unlike steps 0–3 (pure in-memory data transforms), running
  `examples/example.py` sends an actual HTTP request to whatever `provider`/`model` is configured
  in `.boukensha/settings.yaml` (currently `ollama`/`gemma4` in this repo's settings — i.e. it'll
  try `http://localhost:11434/api/chat` and needs a local Ollama server, or will exercise the
  retry-then-`ApiError` path if none is running). Worth calling out explicitly in the verification
  step rather than assuming a clean "it printed some JSON" run.

## Target layout

```
week1_baseline/python/04_api_client/
  boukensha/
    __init__.py            # exports Config, Player, Tool, Message, Context, Registry,
                            #   PromptBuilder, Client, UnknownToolError, UnsupportedModelError, ApiError
    config.py                # from step 3's config.py, PROMPTS_DIR path fixed/unfixed per Q1
    tool.py                   # unchanged copy from 03_prompt_builder
    message.py                 # unchanged copy from 03_prompt_builder
    context.py                  # unchanged copy from 03_prompt_builder
    registry.py                   # unchanged copy from 03_prompt_builder
    prompt_builder.py               # unchanged copy from 03_prompt_builder
    errors.py                        # UnknownToolError, UnsupportedModelError, + new ApiError
    client.py                          # new — Client
    backends/                            # unchanged copy from 03_prompt_builder (all 6 files)
      __init__.py
      base.py
      anthropic.py
      gemini.py
      openai.py
      ollama.py
      ollama_cloud.py
    tasks/
      __init__.py
      base.py               # from 03_prompt_builder, + the settings.is_a?(Hash) guard and .yaml text fix
      player.py             # unchanged copy from 03_prompt_builder
  examples/
    example.py             # from examples/example.rb
  prompts/
    system.md                # this step's own text
  README.md                 # adapted from ruby README + "porting notes" section (per established precedent)
  pyproject.toml
```

## Porting decisions (new for this step)

- **HTTP client: Python's stdlib `http.client`, not `urllib.request` and not `requests`/`httpx`.**
  This directly honors the Ruby README's stated "No Dependencies" intent. The choice between
  `http.client` and `urllib.request` matters more than it looks: `urllib.request.urlopen()`
  *raises* `urllib.error.HTTPError` for any non-2xx response by default, which would force
  exception-based control flow just to inspect a status code for the retryable-status check —
  `http.client.HTTPSConnection`/`HTTPConnection` instead returns a plain response object
  (`.status`, `.read()`) for *any* status, exactly like Ruby's `Net::HTTP#request` — the closest
  structural match to what's being ported, and it keeps `Client.call`'s control flow a direct
  mirror of the Ruby version's `loop`/`break`/`raise` shape. `http.client.HTTPSConnection`
  already builds its own `ssl.create_default_context()` (peer verification on) when none is
  supplied, matching Ruby's `verify_mode = OpenSSL::SSL::VERIFY_PEER` default with zero extra
  code — no equivalent of the commented-out `ca_file`/macOS workaround is needed on the Python
  side.
- **`TRANSIENT_ERRORS` mapping** (no exact 1:1 exists — nearest Python stdlib equivalents):

  | Ruby | Python |
  |---|---|
  | `EOFError`, `SocketError` | `http.client.RemoteDisconnected`, `ConnectionResetError`, `socket.gaierror` |
  | `Errno::ECONNRESET` | `ConnectionResetError` |
  | `Errno::ECONNREFUSED` | `ConnectionRefusedError` |
  | `Net::OpenTimeout`, `Net::ReadTimeout`, `Timeout::Error` | `TimeoutError` (Python 3.10+ alias of `socket.timeout`; covers both connect- and read-timeouts since `http.client` doesn't split them the way Ruby's `net/http` does) |
  | `OpenSSL::SSL::SSLError` | `ssl.SSLError` |

  Proposed tuple: `(ConnectionResetError, ConnectionRefusedError, TimeoutError, ssl.SSLError,
  socket.gaierror, http.client.RemoteDisconnected, http.client.HTTPException)` — the last one
  (`HTTPException`, the base class for `http.client`'s own protocol-level errors, e.g. malformed
  status lines) as a catch-all for the "something went wrong at the HTTP layer, not a clean
  response" bucket that Ruby's broader `EOFError`/`SocketError` catches were reaching for.
- **`RETRYABLE_STATUS_CODES`** → `frozenset({408, 409, 429, 500, 502, 503, 504})` class attribute
  (Ruby's array `.include?` becomes a set membership check — same semantics, better Big-O, no
  behavior change since order never mattered).
- **`Client.call(self, *, max_output_tokens: int = 1024) -> dict[str, Any]`** — same signature
  shape as `PromptBuilder.to_api_payload`, ports the retry loop as a plain `for attempt in
  range(1, MAX_RETRIES + 2)` (four passes, matching the traced Ruby semantics above) rather than
  a `while True`/`break`, since the total attempt count is a known constant — cleaner Python than
  mirroring Ruby's open-ended `loop do ... end` verbatim.
- **Private helpers `retryable_response?`/`retry_delay`** → `_is_retryable_status(status: int) ->
  bool` and `_retry_delay(attempt: int) -> float`, underscore-prefixed per the convention already
  used for `Registry._context`, `Config._resolve_dir`, etc. (`?` dropped, same precedent as
  `prompt_override?` → `prompt_override`).
- **`ApiError`** — bare `class ApiError(Exception): pass` in `errors.py`, alongside the two
  existing exceptions, no new hierarchy — consistent with how `UnsupportedModelError` was added
  in step 3.

## Open questions

1. **The `PROMPTS_DIR` off-by-one bug (see above) — fix it, or port it faithfully (broken)?**
   Recommendation: **fix it** (use the same `../../prompts` calculation as steps 00/03, i.e.
   `Path(__file__).resolve().parent.parent / "prompts"` — identical to how `python/03_prompt_
   builder/boukensha/config.py` already computes `PROMPTS_DIR`, so this is actually the simplest
   option: copy `config.py` from `03_prompt_builder` completely unchanged). This is different
   from the arity-mismatch bug ported faithfully in step 3 — that one was inert (never triggered
   by the example) and clearly deliberate-looking removed-argument code; this one is a bare
   off-by-one typo with an immediate, visible effect (the shipped default system prompt becomes
   unreachable) and no plausible intentional reading. Still flagging explicitly rather than
   silently fixing, per this project's established practice of surfacing Ruby-source drift
   rather than quietly correcting it. If you'd rather port it broken (for strict source fidelity,
   documenting the bug in the porting notes instead of fixing it), say so and I'll do that
   instead.
2. **HTTP client + exception mapping (see "Porting decisions" above)** — OK with `http.client`
   over `urllib.request`, and the proposed `TRANSIENT_ERRORS` tuple? This is the one area of this
   port without a mechanical 1:1 Ruby source to mirror, so it's worth a sanity check before I
   write it.
3. **Retry-loop shape** — `for attempt in range(1, MAX_RETRIES + 2)` (bounded, recommended) vs.
   a more literal `while True` translation of Ruby's `loop do ... end`. Minor, but flagging since
   it's a visible structural choice in the one genuinely new control-flow-heavy file in this step.

## Suggested execution order (once questions are answered)

1. Scaffold `python/04_api_client/` (package dirs including `backends/`, `pyproject.toml`), same
   shared `python/.venv` convention as prior steps (no per-step editable install).
2. Copy `config.py` from `03_prompt_builder` (per Q1's answer — unchanged copy if fixing the bug,
   or a one-line edit to reproduce the extra `../` if porting it broken).
3. Copy `tool.py`, `message.py`, `context.py`, `registry.py`, `prompt_builder.py`, all of
   `backends/`, and `tasks/player.py` unchanged from `03_prompt_builder`.
4. Update `tasks/base.py`: apply the `settings.yaml` message-text fix and the `isinstance(settings,
   dict)` guard in `_fetch`.
5. Write `errors.py` (`UnknownToolError`, `UnsupportedModelError`, new `ApiError`).
6. Write `client.py` (`Client`), per the answered open questions — `RETRYABLE_STATUS_CODES`,
   `TRANSIENT_ERRORS`, `MAX_RETRIES`, `BASE_RETRY_DELAY`, `call()`, `_is_retryable_status()`,
   `_retry_delay()`.
7. Copy this step's own `prompts/system.md` (not step 3's).
8. Update `boukensha/__init__.py` exports (`Client`, `ApiError` added).
9. Port `examples/example.py`: build `Context` + `Registry`, register `read_file`/
   `list_directory`, add the one user message, pick a backend from `provider` (same `if`/`elif`
   dispatch as step 3's example), build `PromptBuilder` + `Client`, print
   `Config`/`provider`/`model`/target URL, call `client.call()`, pretty-print the raw JSON
   response — run against the existing `week1_baseline/.boukensha/settings.yaml` and compare
   against `ruby/04_api_client/examples/example.rb`'s actual output. **Note this step makes a
   real network call** (current settings point at local `ollama`/`gemma4`) — verification means
   either having a real backend reachable (local `ollama serve`, or a valid API key + provider)
   or confirming the retry/backoff/`ApiError` path triggers correctly when nothing is listening.
10. Write `python/04_api_client/README.md` (design doc + porting-notes section — including the
    `PROMPTS_DIR` fix/no-fix note from Q1 and the HTTP-client/exception-mapping notes from Q2),
    per the established precedent.
11. Add `bin/04_api_client_python`, consistent with `bin/03_prompt_builder_python` and (if/when
    a `bin/04_api_client` Ruby launcher exists — it doesn't yet in this repo) that naming too —
    installing only the shared deps into `python/.venv`.
