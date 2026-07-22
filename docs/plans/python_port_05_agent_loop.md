# Plan: Port `ruby/05_agent_loop` → `python/05_agent_loop`

Status: **approved, not yet implemented**
Date: 2026-07-22

## Scope

1. Port the Ruby `05_agent_loop` step into `week1_baseline/python/05_agent_loop`.
2. Add two launcher scripts:
   - `week1_baseline/bin/05_agent_loop_ruby`
   - `week1_baseline/bin/05_agent_loop_python`

## Naming note

The original request said `python/02_agent_loop`, but the Python tree mirrors the
Ruby tree 1:1 (`00`–`04` already exist and `02` is `02_the_registry`), and the
requested bin scripts are named `05_*`. Target confirmed as **`python/05_agent_loop`**.

## Strategy

Copy `python/04_api_client` as the baseline, then apply the same deltas Ruby
applied going `04_api_client → 05_agent_loop`.

Divergence to preserve: Python `04` already ships a `mammouth` backend that Ruby
does not. Keep it, and give it the same new methods as the other OpenAI-shaped
backends.

## New file

1. **`boukensha/agent.py`** — port of `lib/boukensha/agent.rb`. The `Agent` class:
   - `MAX_ITERATIONS = 25`, `WRAP_UP_OUTPUT_TOKENS = 400`, `WRAP_UP_DIRECTIVE`.
   - `__init__(context, registry, builder, client, task_settings=None, max_iterations=None, max_output_tokens=None)`.
   - `run()` — the counted loop; on `stop_reason == "tool_use"` call `handle_tool_calls`, else return `extract_text`.
   - `wrap_up(reason)` — one tools-disabled terminal call (`tools=[]`,
     `max_output_tokens=WRAP_UP_OUTPUT_TOKENS`); falls back to a deterministic
     message on `ApiError`. Runs outside the counted loop.
   - `handle_tool_calls`, `extract_text`, and the
     `resolve_max_iterations` / `resolve_max_output_tokens` helpers,
     `iteration_limit_reached`, `call_opts`, `fallback_message`.
   - Uses `print()` for the `[iteration n/m]`, `tool call →`, `tool result →` trace.

## Modified files (mirroring the Ruby `04 → 05` deltas)

2. **`message.py`** — widen `content: str` → `content: str | list[dict[str, Any]]`.
   The agent stores assistant messages as raw content-block lists, so this is
   required. Adjust `__repr__` slicing to tolerate non-str content.

3. **`errors.py`** — add `class LoopError(Exception)`.

4. **`prompt_builder.py`** — `to_api_payload(..., tools=None)` passthrough; add
   `parse_response(response)` delegating to `self._backend.parse_response`.

5. **`client.py`** — `call(..., tools=None)`, threaded into `to_api_payload`.

6. **`tasks/base.py`** — add `DEFAULT_MAX_ITERATIONS = 25`,
   `DEFAULT_MAX_OUTPUT_TOKENS = 1024`, classmethods `max_iterations(settings)` /
   `max_output_tokens(settings)`, and an `_integer_setting(settings, key, default)`
   helper (wrapping `int(...)`).

7. **All 6 backends** (`anthropic`, `openai`, `gemini`, `ollama`, `ollama_cloud`,
   `mammouth`):
   - `to_payload(..., tools=None)` → use `tools if tools is not None else self.to_tools(...)`.
   - add `parse_response()` normalizing each provider's response into the common
     shape `{stop_reason: "tool_use" | "end_turn", content: [...]}`.
   - OpenAI-shaped backends (`openai`, `ollama`, `ollama_cloud`, `mammouth`) and
     `gemini`: handle the `assistant` role in `to_messages` via an
     `assistant_message()` / `assistant_parts()` rebuild (inverse of
     `parse_response`). Anthropic passes list content through unchanged.
   - Gemini/Ollama/OllamaCloud reuse the function name as the call id.
   - OpenAI/Ollama gain a `json` import for `arguments` (de)serialization.

8. **`__init__.py`** — export `Agent` and `LoopError`; update `__all__`.

9. **`examples/example.py`** — rewrite to mirror the new `example.rb`:
   - `base_dir` anchoring; `read_file` / `list_directory` resolve paths against it.
   - Prompt: "Read the README.md file and summarise what this MUD player assistant
     framework can do."
   - Build the `Agent` with `task_settings=player_settings`.
   - Header `=== BOUKENSHA Step 5: Agent Loop ===`; print max-iterations and
     max-output-tokens; run `agent.run()`; print `=== FINAL RESPONSE ===` + result.

10. **Config-only carry-over:** `README.md`, `prompts/system.md`, `pyproject.toml`,
    `py.typed`. Diff `prompts/system.md` (Ruby 04 → 05) and only change if it
    differs. The Ruby `config.rb` change was cosmetic (endless-method syntax) — no
    Python change needed.

## bin scripts

11. **`bin/05_agent_loop_ruby`** — clone of `bin/04_api_client_ruby`:
    `cd .../ruby/05_agent_loop && bundle exec ruby examples/example.rb`.

12. **`bin/05_agent_loop_python`** — clone of `bin/04_api_client_python`: shared-venv
    bootstrap (`python/.venv`, installs only `python-dotenv` + `PyYAML`), then
    `exec .venv/bin/python 05_agent_loop/examples/example.py`.

Both scripts `chmod +x`.

## Verification

13. Byte-compile the package (`python -m compileall python/05_agent_loop/boukensha`).
14. Run `bin/05_agent_loop_ruby` and `bin/05_agent_loop_python` side-by-side against
    the same `.boukensha/` directory and compare the iteration trace and final output.
