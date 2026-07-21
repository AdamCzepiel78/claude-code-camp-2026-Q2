# 04 · The API Client (Python port)

Python 3 port of [`ruby/04_api_client`](../../ruby/04_api_client/README.md). Same design — see
the Ruby README for the full considerations and sample raw responses per backend. This document
covers the Python-specific implementation and how it differs from the Ruby source.

`Client` takes the payload assembled by `PromptBuilder` and sends it to the API: one HTTP POST,
one response. No tool-calling loop yet — that's step 5. This is also the first step in the port
that performs real I/O: running `examples/example.py` sends an actual HTTP request to whatever
`provider`/`model` is configured in `.boukensha/settings.yaml`.

```
PromptBuilder
      ↓
Client
      ↓
POST to API endpoint
      ↓
Raw JSON response
```

## New files (vs. step 3)

| File | Purpose |
|---|---|
| `boukensha/client.py` | `Client` — makes the HTTP request, retries, parses the response |
| `prompts/system.md` | This step's own default system prompt (different text from step 3's) |

`boukensha/errors.py` gains `ApiError` alongside `UnknownToolError`/`UnsupportedModelError`.
Everything else — `config.py`, `tool.py`, `message.py`, `context.py`, `registry.py`,
`prompt_builder.py`, all five backends, `tasks/player.py` — carries forward unchanged from
`03_prompt_builder` (the Ruby sources are byte-identical, confirmed via `diff -rq`).
`tasks/base.py` carries forward with two small changes — see "What's different" below.

## `boukensha.client.Client`

| Method | Description |
|---|---|
| `Client(builder)` | Wraps a `PromptBuilder` |
| `call(*, max_output_tokens=1024)` | POSTs the payload and returns the parsed JSON response |

**No third-party HTTP library — stdlib `http.client` only, by design.** The Ruby README states
this explicitly: `net/http`, no gems, "to keep things explainable... the HTTP call itself is
trivial and should be visible, not hidden behind a library." The Python port honors the same
constraint (no `requests`, no `httpx`).

### Retries

| Constant | Value |
|---|---|
| `RETRYABLE_STATUS_CODES` | `{408, 409, 429, 500, 502, 503, 504}` |
| `MAX_RETRIES` | `3` |
| `BASE_RETRY_DELAY` | `0.5` seconds, exponential backoff (`0.5s, 1.0s, 2.0s`) |

Up to **4 total attempts** before giving up — sleeps happen only before attempts 2, 3, and 4,
never after the 4th. This applies uniformly whether failures come from a transient network
exception (connection reset/refused, timeout, TLS error, DNS failure) or a retryable HTTP status
code. A final failure raises `ApiError` — with the underlying exception's type/message for
network failures, or the status code + response body for a persistent bad status. Any
non-2xx response (retryable or not) that survives to the end of the loop also raises `ApiError` —
BOUKENSHA surfaces failures explicitly rather than returning `None` or a partial response.

Verified directly against a local test HTTP server (immediate success, retry-then-succeed on
`429`, persistent `500` → `ApiError` after ~3.5s of backoff, connection-refused → `ApiError`
after the same backoff, and an immediate non-retryable `400` → `ApiError` with no retry at all)
and against a real local Ollama server for byte-for-byte parity with the Ruby example's error
output.

### SSL

`http.client.HTTPSConnection` builds its own `ssl.create_default_context()` (peer verification
on) whenever none is supplied — matching Ruby's `verify_mode = OpenSSL::SSL::VERIFY_PEER` default
for free. There's no Python equivalent needed for the commented-out `ca_file`/macOS cert-path
workaround in the Ruby source; Python's default SSL context finds system certs automatically on
every platform this targets.

## Code layout

| File | Purpose | Carried forward from |
|------|---------|------|
| `boukensha/config.py` | `Config` class, incl. `PROMPTS_DIR` | `03_prompt_builder` (unchanged — see below) |
| `boukensha/tasks/base.py` | Abstract `Base` task | `03_prompt_builder`, + a `_fetch` guard (see below) |
| `boukensha/tasks/player.py` | Concrete `Player` task | `03_prompt_builder` (unchanged) |
| `boukensha/tool.py`, `message.py`, `context.py`, `registry.py`, `prompt_builder.py` | Unchanged structs/classes | `03_prompt_builder` (unchanged) |
| `boukensha/backends/*.py` | `Base` + five concrete backends | `03_prompt_builder` (unchanged) |
| `boukensha/errors.py` | `UnknownToolError`, `UnsupportedModelError`, new `ApiError` | new this step |
| `boukensha/client.py` | `Client` | new this step |
| `boukensha/__init__.py` | Top-level package exports | port of `lib/boukensha.rb` |
| `examples/example.py` | Runnable example (makes a real HTTP request) | port of `examples/example.rb` |
| `pyproject.toml` | Package metadata + the two runtime dependencies (`python-dotenv`, `PyYAML`) |

## What's different from step 3

- **`tasks/base.py`: two small changes**, ported directly (no open decision):
  1. The `provider`/`model`-required error messages already said `settings.yaml` in this port
     (the Ruby source's step-3→step-4 change was `settings.yml` → `settings.yaml`, a typo fix —
     nothing to change here since the Python port never had the typo).
  2. `_fetch` gained a guard: `if not isinstance(settings, dict): return None`, so passing a
     non-dict `settings` (e.g. `None`, from `Config.tasks("unknown_task")`) degrades to the
     existing `provider`/`model`-required `ValueError` instead of crashing with an
     `AttributeError` on `.get()` deeper in the call chain.
- **A likely off-by-one bug in the Ruby source's `PROMPTS_DIR` was *not* ported.** Diffing
  `ruby/03_prompt_builder/lib/boukensha/config.rb` against `ruby/04_api_client/lib/boukensha/
  config.rb`, the only change is `File.expand_path("../../prompts", __dir__)` →
  `File.expand_path("../../../prompts", __dir__)` — one extra `../`. Both files live at the same
  relative depth (`lib/boukensha/config.rb`), so the extra `../` walks one directory too far:
  verified directly with `File.expand_path`/`File.exist?` that it resolves to
  `week1_baseline/ruby/prompts`, which doesn't exist. Left as-is this would silently break the
  shipped default system prompt (`Tasks::Player.system_prompt` falls back to `None` under
  default settings) with no crash and no error message — a real, visible functional regression,
  not just cosmetic doc/code drift. Treated as an unintentional typo rather than a deliberate
  change: **this step's `config.py` stays byte-identical to `03_prompt_builder`'s** (the correct
  `PROMPTS_DIR` calculation), rather than reproducing the bug.
- **New `prompts/system.md` text** for this step (different persona copy from step 3's) — shipped
  verbatim, same pattern as prior steps' per-step prompt text.

## Porting notes (deviations from the Ruby source)

Carries forward every convention already established in prior steps' READMEs (symbol/string key
collapse, `Path`-based paths, decorator-based `Registry.tool`, `model_info`/`model_info_for`
naming split, full type hints, no `abc.ABC`, etc.) — not repeated here. New for this step:

- **`http.client` over `urllib.request`.** `urllib.request.urlopen()` raises
  `urllib.error.HTTPError` for any non-2xx response by default, which would force
  exception-based control flow just to read a status code for the retryable-status check.
  `http.client.HTTPSConnection`/`HTTPConnection` instead returns a plain response object
  (`.status`, `.read()`) for *any* status — the closest structural match to Ruby's
  `Net::HTTP#request`, and it keeps `Client.call`'s control flow a direct mirror of the Ruby
  version's loop/break/raise shape.
- **`TRANSIENT_ERRORS` mapping** — no exact 1:1 exists for Ruby's exception list. Mapped as:
  `ConnectionResetError` (← `Errno::ECONNRESET`), `ConnectionRefusedError` (←
  `Errno::ECONNREFUSED`), `TimeoutError` (← `Net::OpenTimeout`/`Net::ReadTimeout`/
  `Timeout::Error` — Python doesn't split connect- vs read-timeouts the way Ruby's `net/http`
  does), `ssl.SSLError` (← `OpenSSL::SSL::SSLError`), `socket.gaierror` (← `SocketError`),
  `http.client.RemoteDisconnected` (← `EOFError`, server closed the connection unexpectedly), and
  `http.client.HTTPException` as a catch-all for other HTTP-protocol-level errors.
- **`RETRYABLE_STATUS_CODES`** is a `frozenset[int]`, not a list — same membership semantics as
  Ruby's `Array#include?`, better complexity, no behavior change (order never mattered).
- **Retry loop** ported as a bounded `for attempt in range(1, MAX_RETRIES + 2)` (4 passes) rather
  than a literal translation of Ruby's open-ended `loop do ... end`, since the total attempt
  count is a fixed constant — verified to reproduce the exact same attempt-count/backoff-timing
  semantics as the Ruby source (see "Retries" above).
- **Private helpers `retryable_response?`/`retry_delay`** → `_is_retryable_status`/
  `_retry_delay`, underscore-prefixed per this port's established convention (`?` dropped, same
  precedent as `prompt_override?` → `prompt_override`).
- **`ApiError`** — bare `class ApiError(Exception): pass`, no new hierarchy, consistent with how
  `UnsupportedModelError` was added in step 3.

## Shared venv, no per-step install

Same as prior steps: `python/.venv` is shared only for the two third-party runtime deps
(`python-dotenv`, `PyYAML`) — `http.client`, `ssl`, `socket`, and `urllib.parse` are all stdlib.
This step's own `boukensha` package is never `pip install`-ed — `examples/example.py` loads it
via `sys.path` insertion instead, mirroring Ruby's per-step `require_relative "../lib/boukensha"`.

## Setup

Requires Python ≥ 3.11.

```bash
cd week1_baseline/python
python3 -m venv .venv
source .venv/bin/activate
pip install "python-dotenv>=1.0" "PyYAML>=6.0"
```

## Run example

```bash
./week1_baseline/bin/04_api_client_python
```

This bootstraps `python/.venv` on first run and is safe to re-run any time. Or, with the shared
venv active:

```bash
python 04_api_client/examples/example.py
```

**This sends a real HTTP request** to the `provider`/`model` configured in your
`.boukensha/settings.yaml` — either point it at a reachable backend (a local `ollama serve`, or a
valid API key for `anthropic`/`openai`/`gemini`/`ollama_cloud`), or expect it to exhaust its
retries and raise `ApiError`. Sample output against a working Anthropic backend, from the Ruby
README (Python output is the same shape, `Config`'s `repr()` differs only in the module path
prefix already established in prior steps):

```
=== BOUKENSHA Step 4: API Client ===

Config: #<Boukensha.Config dir=/home/andrew/Sites/Claude-Code-Camp/.boukensha tasks=player>
Provider: anthropic
Model: claude-opus-4-8
Sending request to https://api.anthropic.com/v1/messages...

Raw response:
{
  "model": "claude-opus-4-8",
  "id": "msg_01Y3zL8dZKrdLqry6BoiyC4r",
  "type": "message",
  "role": "assistant",
  "content": [
    {
      "type": "text",
      "text": "I don't have a function available to list directory contents..."
    }
  ],
  "stop_reason": "end_turn",
  "usage": { "input_tokens": 585, "output_tokens": 118 }
}
```
