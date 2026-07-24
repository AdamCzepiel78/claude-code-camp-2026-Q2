# Mammouth-AI-Backend: Implementierungszusammenfassung (nachträglich)

> Nachträglich dokumentierter Plan — beschreibt, was tatsächlich umgesetzt wurde, um
> [Mammouth AI](https://mammouth.ai/) als LLM-Backend in Boukensha zu ergänzen.

## Kontext

Der Boukensha-Agent bindet seinen `player`-Task über austauschbare **Backends** an
verschiedene LLM-APIs (Anthropic, Gemini, OpenAI, Ollama, OllamaCloud). Ziel war, Mammouth AI
als weiteres Backend zu ergänzen, um dessen breite Modellpalette (Claude, GPT, Gemini, Mistral,
Grok, DeepSeek, Qwen, Kimi …) über ein einziges Abo/API nutzen zu können.

**Entscheidende Erkenntnis:** Mammouth ist **OpenAI-kompatibel**.

- Endpoint: `https://api.mammouth.ai/v1/chat/completions`
- Auth: Header `Authorization: Bearer <API_KEY>`
- Request-/Response-Format: identisch zur OpenAI Chat Completions API
- Modell-Liste (Recherche): `https://api.mammouth.ai/public/models`

Dadurch ist das `Mammouth`-Backend praktisch eine Kopie des bestehenden `OpenAI`-Backends —
nur mit anderer `BASE_URL`, eigener `MODELS`-Tabelle und dem Payload-Feld `max_tokens` statt
`max_completion_tokens`. Serialisierung von Messages/Tools (`role: "system"`-Message,
`function`-gewrappte Tools, `role: "tool"` für Tool-Results) blieb unverändert.

**Umfang:** alle vier Ziele — Python **und** Ruby, jeweils in `03_prompt_builder` **und**
`04_api_client` (Backends existieren als eigenständige Kopien pro Schritt).

## Umgesetzte Änderungen

### 1. Neues Backend (4 neue Dateien)

Kopie des jeweiligen OpenAI-Backends, angepasst: Klassenname `Mammouth`,
`BASE_URL = "https://api.mammouth.ai/v1/chat/completions"`, kuratierte `MODELS`-Tabelle,
Payload-Feld `max_tokens`. `to_messages` / `to_tools` / `headers` / `url` unverändert.

- `week1_baseline/python/03_prompt_builder/boukensha/backends/mammouth.py`
- `week1_baseline/python/04_api_client/boukensha/backends/mammouth.py`
- `week1_baseline/ruby/03_prompt_builder/lib/boukensha/backends/mammouth.rb`
- `week1_baseline/ruby/04_api_client/lib/boukensha/backends/mammouth.rb`

### 2. Wiring / Export (4 Dateien)

- Python `…/boukensha/backends/__init__.py` (Schritt 03 + 04): Import von `Mammouth` +
  Aufnahme in `__all__`.
- Ruby `…/lib/boukensha.rb` (Schritt 03 + 04): `require_relative "boukensha/backends/mammouth"`.

### 3. Provider-Dispatch in den Beispielen (4 Dateien)

- Python `…/examples/example.py` (Schritt 03 + 04): Import um `Mammouth` erweitert und Zweig
  ```python
  elif provider == "mammouth":
      backend = Mammouth(api_key=os.environ["MAMMOUTH_API_KEY"], model=model)
  ```
- Ruby `…/examples/example.rb` (Schritt 03 + 04): `case`-Zweig
  ```ruby
  when "mammouth"
    Boukensha::Backends::Mammouth.new(api_key: ENV.fetch("MAMMOUTH_API_KEY"), model: model)
  ```
  (stil-konsistent: einzeilig in Schritt 03, mehrzeilig in Schritt 04).

### 4. Konfiguration (User-seitig)

- `week1_baseline/.boukensha/.env`: `MAMMOUTH_API_KEY=<key>` ergänzt.
- `week1_baseline/.boukensha/settings.yaml`: `provider: mammouth`, `model: mistral-large-3`.

### 5. Nebenbei behoben: doppelter Ollama-Modellschlüssel

`week1_baseline/ruby/03_prompt_builder/lib/boukensha/backends/ollama.rb` enthielt `gemma3:12b`
doppelt (zwei Einträge mit unterschiedlichem `context_window`), was eine Ruby-Warnung
„key is duplicated and overwritten" auslöste. Das Duplikat wurde entfernt → jetzt konsistent
zu den anderen drei Ollama-Backend-Dateien (`gemma3:12b` mit `context_window: 128_000`).

## Kuratierte `MODELS`-Tabelle

Werte aus `api.mammouth.ai/public/models`. Nur Text-/Tool-fähige Modelle; Bild-
(`gpt-image-2`, `*-image-*`) und Embedding-Modelle (`text-embedding-*`) bewusst ausgeschlossen.
Kosten pro **1 Mio. Tokens** (API liefert pro-Token in wiss. Notation, z. B. `$5e-6` → `5.0`).
`usage_unit: tokens` durchgehend.

| Modell | context_window | input | output |
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

## Design-Entscheidungen

- **`max_tokens` statt `max_completion_tokens`.** Die Mammouth-Doku listet explizit `max_tokens`.
  Da Mammouth ein OpenAI-kompatibler Proxy vor vielen Anbietern (Anthropic, Google …) ist, ist
  das klassische, breit unterstützte `max_tokens` die sicherere Wahl. Einzige funktionale
  Abweichung von der OpenAI-Vorlage in `to_payload` (der Methodenparameter heißt weiterhin
  `max_output_tokens` — nur der ausgehende JSON-Schlüssel ist `max_tokens`).
- **Klassenname `Mammouth`**, Provider-String `"mammouth"`, Env-Variable `MAMMOUTH_API_KEY` —
  konsistent zum Muster der übrigen Backends.
- **Backend-Metadaten** (`context_window`, `estimate_cost`, `usage_unit` …) funktionieren
  automatisch über die geerbte `Base`-Logik, sobald `MODELS` befüllt ist.
- **Kuratierte statt vollständige Modell-Liste** (~80 Modelle in der API): nur die 12 wichtigsten
  Text-/Tool-Modelle, für Übersicht und weil Bild-/Embedding-Modelle ohnehin nicht chat-/tool-
  fähig sind.

## Verifikation (durchgeführt)

| Test | Python 03 | Python 04 | Ruby 03 | Ruby 04 |
|---|---|---|---|---|
| Modell-Validierung + `UnsupportedModelError` bei unbekanntem Modell | ✅ | ✅ | ✅ | ✅ |
| Payload: `max_tokens` vorhanden, `max_completion_tokens` **nicht**, system+tool-Messages korrekt | ✅ | ✅ | ✅ | ✅ |
| `estimate_cost` / `context_window` / `url` | ✅ | ✅ | ✅ | ✅ |
| bin-Launcher (voller Dispatch-Pfad) | ✅ | ✅ | ✅ | ✅ |

- **Schritt 03** (`bin/03_prompt_builder_{python,ruby}`): baut den Payload für
  `provider: mammouth` sauber, keine Ruby-Warnung mehr.
- **Schritt 04** (`bin/04_api_client_{python,ruby}`): **echter** API-Call an
  `https://api.mammouth.ai/v1/chat/completions` mit gültigem Key → exit 0, echte
  OpenAI-kompatible `chat.completion`-Antwort. Das Modell (Mistral über Mammouth) sah die
  registrierten Tools und antwortete mit `finish_reason: "tool_calls"` (wollte
  `list_directory` aufrufen). Erwartetes Verhalten für Schritt 04 — das eigentliche Tool-Loop
  folgt erst in Schritt 05.

## Betroffene Dateien (Übersicht)

**Neu (4):** `…/backends/mammouth.py` (×2), `…/backends/mammouth.rb` (×2)
**Geändert (9):** `…/backends/__init__.py` (×2), `…/lib/boukensha.rb` (×2),
`…/examples/example.py` (×2), `…/examples/example.rb` (×2),
`ruby/03_prompt_builder/lib/boukensha/backends/ollama.rb` (Duplikat-Fix)
**Konfiguration (2, User-seitig):** `.boukensha/.env`, `.boukensha/settings.yaml`
