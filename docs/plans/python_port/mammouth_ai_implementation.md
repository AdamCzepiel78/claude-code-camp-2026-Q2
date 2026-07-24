# Mammouth-AI Backend: Implementation Summary (retrospective)

> Retrospectively documented plan — describes what was actually done to add
> [Mammouth AI](https://mammouth.ai/) as an LLM backend in Boukensha.
> German version: [`mammouth_ai_implementation_german.md`](./mammouth_ai_implementation_german.md).

## Context

The Boukensha agent binds its `player` task to different LLM APIs through pluggable **backends**
(Anthropic, Gemini, OpenAI, Ollama, OllamaCloud). The goal was to add Mammouth AI as another
backend, giving access to its broad model lineup (Claude, GPT, Gemini, Mistral, Grok, DeepSeek,
Qwen, Kimi …) through a single subscription/API.

**Key finding:** Mammouth is **OpenAI-compatible**.

- Endpoint: `https://api.mammouth.ai/v1/chat/completions`
- Auth: header `Authorization: Bearer <API_KEY>`
- Request/response format: identical to the OpenAI Chat Completions API
- Model list (research): `https://api.mammouth.ai/public/models`

That makes the `Mammouth` backend essentially a copy of the existing `OpenAI` backend — only
with a different `BASE_URL`, its own `MODELS` table, and the payload field `max_tokens` instead
of `max_completion_tokens`. Message/tool serialization (`role: "system"` message,
`function`-wrapped tools, `role: "tool"` for tool results) was left unchanged.

**Scope:** all four targets — Python **and** Ruby, in both `03_prompt_builder` **and**
`04_api_client` (backends exist as standalone copies per step).

## Changes made

### 1. New backend (4 new files)

Copy of the respective OpenAI backend, adapted: class name `Mammouth`,
`BASE_URL = "https://api.mammouth.ai/v1/chat/completions"`, curated `MODELS` table, payload field
`max_tokens`. `to_messages` / `to_tools` / `headers` / `url` unchanged.

- `week1_baseline/python/03_prompt_builder/boukensha/backends/mammouth.py`
- `week1_baseline/python/04_api_client/boukensha/backends/mammouth.py`
- `week1_baseline/ruby/03_prompt_builder/lib/boukensha/backends/mammouth.rb`
- `week1_baseline/ruby/04_api_client/lib/boukensha/backends/mammouth.rb`

### 2. Wiring / export (4 files)

- Python `…/boukensha/backends/__init__.py` (steps 03 + 04): import `Mammouth` + add to `__all__`.
- Ruby `…/lib/boukensha.rb` (steps 03 + 04): `require_relative "boukensha/backends/mammouth"`.

### 3. Provider dispatch in the examples (4 files)

- Python `…/examples/example.py` (steps 03 + 04): import extended by `Mammouth`, plus the branch
  ```python
  elif provider == "mammouth":
      backend = Mammouth(api_key=os.environ["MAMMOUTH_API_KEY"], model=model)
  ```
- Ruby `…/examples/example.rb` (steps 03 + 04): `case` branch
  ```ruby
  when "mammouth"
    Boukensha::Backends::Mammouth.new(api_key: ENV.fetch("MAMMOUTH_API_KEY"), model: model)
  ```
  (style-consistent: single-line in step 03, multi-line in step 04).

### 4. Configuration (user side)

- `week1_baseline/.boukensha/.env`: added `MAMMOUTH_API_KEY=<key>`.
- `week1_baseline/.boukensha/settings.yaml`: `provider: mammouth`, `model: mistral-large-3`.

### 5. Fixed along the way: duplicate Ollama model key

`week1_baseline/ruby/03_prompt_builder/lib/boukensha/backends/ollama.rb` contained `gemma3:12b`
twice (two entries with different `context_window`), which triggered a Ruby warning
"key is duplicated and overwritten". The duplicate was removed → now consistent with the other
three Ollama backend files (`gemma3:12b` with `context_window: 128_000`).

## Curated `MODELS` table

Values from `api.mammouth.ai/public/models`. Text/tool-capable models only; image
(`gpt-image-2`, `*-image-*`) and embedding models (`text-embedding-*`) deliberately excluded.
Costs are per **1M tokens** (the API returns per-token in scientific notation, e.g. `$5e-6` →
`5.0`). `usage_unit: tokens` throughout.

| Model | context_window | input | output |
|---|---|---|---|
| `claude-sonnet-5` | 1_000_000 | 2.0 | 10.0 |
| `claude-opus-4-8` | 1_000_000 | 5.0 | 25.0 |
| `gpt-5.5` | 1_050_000 | 5.0 | 30.0 |
| `gpt-5.4` | 922_000 | 2.5 | 15.0 |
| `gemini-3.5-flash` | 1_048_576 | 1.5 | 9.0 |
| `gemini-2.5-pro` | 1_048_576 | 2.5 | 15.0 |
| `mistral-large-3` | 262_144 | 0.5 | 1.5 |
| `grok-4.5` | 500_000 | 2.0 | 6.0 |
| `deepseek-v4-pro` | 1_050_000 | 1.74 | 3.48 |
| `qwen3.7-max` | 1_000_000 | 2.5 | 7.5 |
| `kimi-k3` | 1_048_576 | 3.0 | 15.0 |
| `mammouth-recommended` | 1_048_576 | 1.4 | 4.4 |

## Design decisions

- **`max_tokens` instead of `max_completion_tokens`.** Mammouth's docs explicitly list
  `max_tokens`. Since Mammouth is an OpenAI-compatible proxy in front of many providers
  (Anthropic, Google …), the classic, broadly supported `max_tokens` is the safer choice. This is
  the only functional deviation from the OpenAI template in `to_payload` (the method parameter is
  still named `max_output_tokens` — only the outgoing JSON key is `max_tokens`).
- **Class name `Mammouth`**, provider string `"mammouth"`, env variable `MAMMOUTH_API_KEY` —
  consistent with the pattern of the other backends.
- **Backend metadata** (`context_window`, `estimate_cost`, `usage_unit` …) works automatically
  via the inherited `Base` logic once `MODELS` is populated.
- **Curated instead of full model list** (~80 models in the API): only the 12 most important
  text/tool models, for clarity and because image/embedding models aren't chat/tool-capable
  anyway.

## Verification (performed)

| Test | Python 03 | Python 04 | Ruby 03 | Ruby 04 |
|---|---|---|---|---|
| Model validation + `UnsupportedModelError` for unknown model | ✅ | ✅ | ✅ | ✅ |
| Payload: `max_tokens` present, `max_completion_tokens` **absent**, system+tool messages correct | ✅ | ✅ | ✅ | ✅ |
| `estimate_cost` / `context_window` / `url` | ✅ | ✅ | ✅ | ✅ |
| bin launcher (full dispatch path) | ✅ | ✅ | ✅ | ✅ |

- **Step 03** (`bin/03_prompt_builder_{python,ruby}`): builds the payload for
  `provider: mammouth` cleanly, no more Ruby warning.
- **Step 04** (`bin/04_api_client_{python,ruby}`): **real** API call to
  `https://api.mammouth.ai/v1/chat/completions` with a valid key → exit 0, real
  OpenAI-compatible `chat.completion` response. The model (Mistral via Mammouth) saw the
  registered tools and responded with `finish_reason: "tool_calls"` (wanted to call
  `list_directory`). Expected behavior for step 04 — the actual tool loop comes in step 05.

## Affected files (overview)

**New (4):** `…/backends/mammouth.py` (×2), `…/backends/mammouth.rb` (×2)
**Changed (9):** `…/backends/__init__.py` (×2), `…/lib/boukensha.rb` (×2),
`…/examples/example.py` (×2), `…/examples/example.rb` (×2),
`ruby/03_prompt_builder/lib/boukensha/backends/ollama.rb` (duplicate fix)
**Configuration (2, user side):** `.boukensha/.env`, `.boukensha/settings.yaml`
