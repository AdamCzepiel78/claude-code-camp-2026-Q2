# Week 1 - Baseline Technical Documentation

## Technical Goal

Get the Python port of the boukensha agent framework caught up to Ruby, step by step, through the standard tool library, the TUI, and context management. Alongside that, stop treating the MUD as something baked into the client - pull the actual MCP protocol handling out into something generic, so both languages talk to the same MUD server instead of each reimplementing the telnet layer, and so a bootcamper could plug in a completely unrelated MCP server without touching client code.

## Technical Uncertainty

Biggest unknown going in was whether a MUD session even makes sense as a server you talk to over MCP, or whether the per-invocation cost (login alone takes several seconds) would make that approach a non-starter compared to just keeping the telnet logic inline per language. Also wasn't sure how far Ruby's step 11/12 sources had actually drifted from their own READMEs - given how much had already changed under the hood by the time I got to context management, I went in expecting the docs to be roughly accurate and mostly just needed a Python equivalent.

On the TUI side, no idea what would stand in for Ruby's `charm` gem in Python - Textual seemed like the obvious pick but hadn't actually driven Textual's threading model before, so wasn't sure whether the "run a turn in a background thread, update the UI live" pattern the Ruby TUI uses would even translate cleanly.

## Technical Hypotheses

Expected the MUD-as-MCP-server idea to pay off once measured properly - a login is expensive, a follow-up command is cheap, so something has to hold the socket open across calls regardless of language. Figured extracting the transport into its own gem would be mechanical once the split between "MUD-specific" and "generic JSON-RPC plumbing" was clear.

Assumed the Ruby step 12 README was a reasonably complete description of what that step actually does, and that porting it would mostly be "add context-window tracking and compaction, done."

## Technical Observations

**MUD over MCP - the economics turned out to matter more than expected.**
Measured it directly against the live server: logging in costs ~5.9s, a command on an already-open session costs ~0.1s. That's a 61x difference, and the MUD also pushes unsolicited output (you can send nothing and still have over a thousand characters sitting in the buffer three seconds later). Something has to stay alive holding that socket - a per-invocation CLI can't do that, so a long-running MCP server genuinely is the right shape here, not just a convenient abstraction.

**Extracting the transport was cleaner than expected, and paid off almost immediately.**
Once the MUD server's actual domain-specific code got counted, it was only about 14 lines out of 164 - the rest was generic JSON-RPC handshake/dispatch that had nothing to do with MUDs. Pulled that into its own gem (`mcp_server`) with the identity/tools/instructions all injected instead of hardcoded, then proved it was actually generic by building an unrelated 8-line notes server on top of it - no MUD code touched. Ported the same framework to Python too, since the whole point was letting a non-Ruby bootcamper write a server without touching Ruby at all.

**mud_manager_mcp shipping as two gems was a self-inflicted problem I then had to un-inflict.**
After the transport was extracted, installing the MUD server meant installing two gems in the right order, which is exactly the kind of friction a bootcamper trips over. Fixed it by vendoring the transport's three files directly into mud_manager_mcp with a drift-check script comparing them against the canonical source, so it ships as one dependency-free gem again while the reusable framework still exists separately for anyone who wants to build their own server. Only caught the fact that this actually needed fixing by testing the *installed* gem, not the checkout - running from a checkout hid a path-resolution bug that the installed version exposed immediately (the MUD tool preset was computing a relative path assuming a sibling checkout existed, which isn't true once you're inside `gem install`'s directory - added a `Gem.bin_path` fallback).

**Multi-server support and collision namespacing.**
Wanted more than one MCP server pluggable at once without one silently stomping the other's tool names. Landed on: only namespace a tool name (`server__tool`) if it actually collides across servers, leave everything else exactly as the server published it. Proved this by connecting the same server twice under different keys and confirming they kept separate state and both sets of instructions ended up in the system prompt.

**Porting the TUI to Python meant picking Textual, and that decision paid for itself once but bit once too.**
Textual's `@work(thread=True)` + `call_from_thread` turned out to be a genuinely clean replacement for the Ruby side's manual thread + queue draining. The one real gotcha: `call_from_thread` throws if you call it while you're *already* on the UI thread, which happens whenever a slash command triggers output directly instead of from the background worker (e.g. Ctrl+L). Had to check `get_current_worker()`/`NoActiveWorker` and branch on which thread was actually calling. Only found this because I ran the thing through Textual's headless test harness rather than trusting the code by inspection - it failed immediately and made the bug obvious.

**Step 12 was a lot more than its own README described.**
The Ruby README for context management only talks about context-window tracking, compaction, and the colour-coded usage bar. Diffing the actual source against the previous step showed four more things the README never mentions: reasoning-block plumbing added across every backend, OpenAI's backend switched entirely from Chat Completions to the Responses API, the whole per-task settings abstraction (`Tasks::Base`/`Tasks::Player`) got deleted in favor of reading straight from config, and the `mammouth` backend got dropped outright. None of that is a small step. Decided to keep `mammouth` in the Python port on request even though Ruby dropped it, which then surfaced its own problem: the model-name-to-context-window lookup Ruby uses breaks the moment the same model name means two different things under two different backends (`claude-haiku-4-5` is 200k tokens directly against Anthropic, 1M through the mammouth proxy). Fixed it properly by resolving the backend first and reading its own per-model table directly, instead of a shared table keyed only on model name.

**Reasoning-block support turned out to be defensive plumbing, not a feature switch.**
Every backend now normalizes a "reasoning" content block if a provider hands one back, but checking every actual outgoing request confirmed none of them turn thinking on by default - Gemini explicitly disables it, Ollama sends `think: false`, OpenAI requests `effort: none`, Anthropic never asks for it at all. So the whole thing is there so a reasoning block gets handled correctly *if* one shows up, not because this step makes the agent visibly think.

**Found a real, live-confirmed bug in the context-tracking feature itself, inherited from Ruby.**
Tested compaction against the real mammouth API with a deliberately tiny context window and it never fired. Turned out the token-accounting code reads `usage["input_tokens"]` with no per-provider normalization, and mammouth's actual usage field is shaped `prompt_tokens`/`completion_tokens` instead. Checked Ruby's source directly - same exact read, same problem, and it also affects Gemini (`usageMetadata`, not `usage`) and Ollama (`prompt_eval_count`/`eval_count` sitting at the top level, no `usage` key at all). So the headline feature of this step - context tracking and auto-compaction - only actually functions for Anthropic in Ruby's own current source. Left it as-is rather than quietly fixing it, since that's a real design call bigger than what I was asked to decide, and flagged it clearly instead.

## Technical Conclusions

The MUD-over-MCP hypothesis held up under actual measurement, which made the whole "extract a generic transport" effort feel justified rather than speculative. The bigger lesson though was that a step's own documentation isn't a reliable map of what the step actually does once code has kept moving after the README was written - diffing against source directly caught real, substantial functionality (the Responses API migration, the reasoning plumbing) that reading the README alone would have missed entirely, and that pattern held twice in one week.

New uncertainty worth carrying forward: the context-tracking bug means auto-compaction can't be trusted for anything except Anthropic right now, in either language, and that's not something I fixed - just documented. Also open: whether the Ruby README for step 12 should get updated to match its own source, which is a reasonable follow-up but a separate piece of work from porting.

## Key Takeaway

Measure the actual cost before assuming an architecture is right, and diff against source instead of trusting a step's own README - both times that discipline turned up something a good-faith read would have missed.
