# Plan: ship `mud_manager_mcp` as a single self-contained gem

Status: **implemented (Approach A) and verified — see "Outcome" below**
Date: 2026-07-24

## Outcome — 2026-07-24

Executed with **Approach A** (vendor the transport, keep the standalone gem).

- `McpServer` vendored byte-identical under
  `mud_manager_mcp/lib/vendor/{mcp_server.rb,mcp_server/server.rb,mcp_server/tool_table.rb}`,
  with a provenance `lib/vendor/README.md`. Layout tweak vs. the draft: vendored
  under `lib/vendor/` (not a top-level `vendor/`), so the existing
  `Dir["lib/**/*.rb"]` glob already packages it — no `spec.files` change needed.
- `lib/mud_manager_mcp.rb` now `require_relative "vendor/mcp_server"`;
  `bin/mud_manager_mcp` dropped the `mcp_server` load-path line and the separate
  `require "mcp_server"`; the gemspec dropped `add_dependency "mcp_server"`.
- Drift guard added: `tasks/verify_vendor.rb` diffs the copies against
  `../mcp_server/lib` and exits non-zero on any difference (passes).
- Decision 4: `week0_explore/mud_manager` left as-is (out of shipping scope).

Verified: built gem lists **zero dependencies** (`--- []`); with the
`mcp_server` **gem uninstalled**, the installed `bin/mud_manager_mcp` still
serves a live handshake (`mud-manager v0.1.0`) and `tools/list` → 31 tools;
steps 10/11/12 all register 31 MUD tools over MCP and resolve `look` live; the
installed `boukensha` binary boots with the MUD reachable. The standalone
`mcp_server` gem/dir remains as the canonical source and teaching artifact.

## Context

Installing the MUD MCP server today pulls **two** gems:

```
mud_manager_mcp   (Session, Primitives, SessionRegistry, Tools, ToolProvider, bin/)
      └── depends on ──▶ mcp_server   (Server, ToolTable — the generic transport)
```

`mud_manager_mcp.gemspec` has exactly one dependency, `add_dependency
"mcp_server", "~> 0.1"`, and `bin/mud_manager_mcp` does `require "mcp_server"`.
So shipping the server means shipping two gems, and a user who just wants "the
MUD MCP binary" has to build and install both, in order, before it runs.

The goal of this plan: **one gem, one binary.** `gem install mud_manager_mcp`
should pull nothing else, and `bin/mud_manager_mcp` should run from that one gem
alone.

### The honest tension

We *deliberately extracted* `mcp_server` a short while ago (see
[`generic_mcp_server.md`](generic_mcp_server.md)). The point of that split was
reuse: a bootcamper can `require "mcp_server"` and stand up their **own** MCP
server without copying code out of a MUD project, and there is a matching
Python port (`python/mcp_server/`) so non-Ruby bootcampers can do the same.

Folding the transport back into `mud_manager_mcp` trades that reuse story for
deployment simplicity. This is a real trade-off, not a free win, so the plan is
built around **preserving both** where possible — single-binary shipping *and*
a still-reusable framework — and names the one place a genuine either/or
decision has to be made (whether the standalone `mcp_server` gem survives).

### What "mud_manager" refers to

Three directories carry the name; only one is the target here:

| Path | What it is | In scope? |
| --- | --- | --- |
| `week1_baseline/mud_manager_mcp/` | The MCP server gem — **the target** | yes |
| `week1_baseline/mcp_server/` | The generic transport gem it depends on | yes (absorbed) |
| `week0_explore/mud_manager/` | The original pre-MCP library (`Initial commit` only, a stale ancestor) | no |
| `week1_baseline/python/mud_manager/` | Python in-process session port (the `mud_mcp=False` fallback) | no |

"The actual Mud Manager" = `mud_manager_mcp`. "The MCP server" being folded in =
the `mcp_server` gem.

---

## What actually causes "two gems"

Just two lines:

1. `mud_manager_mcp.gemspec`: `spec.add_dependency "mcp_server", "~> 0.1"`
2. `bin/mud_manager_mcp`: `require "mcp_server"` (plus a `$LOAD_PATH.unshift
   ../../mcp_server/lib` so it also runs straight from a checkout)

`mcp_server` is small — **276 lines across three files**
(`mcp_server.rb` 21, `server.rb` 189, `tool_table.rb` 66) and has **zero
external dependencies** of its own. That makes it cheap to absorb.

Nothing else in the repo depends on the `mcp_server` gem: a grep for a real
`require "mcp_server"` / `add_dependency "mcp_server"` outside `mud_manager_mcp`
returns nothing. Everywhere else, the string `mcp_server` is the boukensha
`mcp_servers:` **config key** or a prose mention — not a load. So absorbing the
transport touches exactly one consumer.

---

## Approaches

Three ways to reach one gem, from least to most destructive to the extraction.

### (A) Vendor the transport into `mud_manager_mcp`, keep the standalone gem — **recommended**

Copy the three `mcp_server` files into `mud_manager_mcp`'s own tree, drop the
gemspec dependency and the `require "mcp_server"`. The standalone
`week1_baseline/mcp_server/` gem stays exactly as it is — the canonical source,
the teaching artifact, the thing the Python port mirrors.

- **Ships as one gem.** `mud_manager_mcp` no longer names any dependency.
- **Reuse story intact.** Someone writing their own server still uses the
  standalone gem; nothing about that changed.
- **Cost:** the 276 lines now exist in two places. They can drift. Mitigated by
  keeping them byte-identical and adding a one-line pointer comment in each copy
  saying the canonical source is `week1_baseline/mcp_server/`, plus a CI/verify
  step (or a rake task) that diffs the two and fails if they diverge.

### (B) Absorb and delete the standalone gem

Move the transport into `mud_manager_mcp`, then delete
`week1_baseline/mcp_server/` (and, for symmetry, `python/mcp_server/`).

- **One source of truth, one gem.** No duplication.
- **Loses** the reusable framework, the "write your own MCP server" teaching
  path, and the Ruby/Python framework symmetry we just built. This directly
  reverses `generic_mcp_server.md`.
- Choose this only if the generic framework is *not* wanted as a product.

### (C) Bundle the standalone gem's files into the one `.gem` without moving them

Keep `mcp_server/` where it is, but have `mud_manager_mcp.gemspec` reach across
and package `../mcp_server/lib/**/*.rb` into the built gem, dropping the
dependency.

- One installable gem, no duplication in the *source* tree.
- **Rejected:** a gemspec that globs files from a sibling directory outside its
  own root is fragile (breaks under `gem build` from anywhere the sibling isn't
  present, breaks packaging assumptions, surprises the next reader). Not worth
  it.

**Recommendation: (A).** It delivers the stated goal — one gem, one binary —
without throwing away the extraction we just did. The only real downside,
duplication, is 276 dependency-free lines guarded by a diff check.

---

## Recommended implementation (Approach A)

### 1. Vendor the transport

Copy the three files into `mud_manager_mcp`, under a `vendor/` path that makes
their origin obvious and keeps them out of the `MudManagerMcp` namespace's own
files:

```
week1_baseline/mud_manager_mcp/
  lib/
    mud_manager_mcp.rb
    mud_manager_mcp/
      … existing session/primitives/tools/tool_provider …
    vendor/
      mcp_server.rb          # copies of the canonical files, unchanged
      mcp_server/
        server.rb
        tool_table.rb
```

Keep the `McpServer` module name unchanged — the code `bin/mud_manager_mcp`
already calls (`McpServer::Server.new(...)`) keeps working verbatim. Add a
header comment to each vendored file:

```ruby
# Vendored from week1_baseline/mcp_server (the canonical, standalone gem).
# Do not edit here — edit there and re-copy. A verify task checks the two match.
```

### 2. Load the vendored copy instead of the gem

`lib/mud_manager_mcp.rb` gains, before its other requires:

```ruby
require_relative "../vendor/mcp_server"
```

`bin/mud_manager_mcp` drops both the `$LOAD_PATH.unshift ../../mcp_server/lib`
line and the standalone `require "mcp_server"` — the transport now arrives
through `require "mud_manager_mcp"`.

### 3. Drop the dependency

`mud_manager_mcp.gemspec`:

- remove `spec.add_dependency "mcp_server", "~> 0.1"`
- widen `spec.files` to include the vendored tree:
  `Dir["lib/**/*.rb"] + Dir["vendor/**/*.rb"] + Dir["bin/*"]`
- note in `spec.description` that the transport is vendored, so the gem is
  self-contained with no runtime dependencies.

### 4. Guard against drift

Add `mud_manager_mcp/tasks/verify_vendor.rb` (or a rake task) that diffs
`vendor/mcp_server*` against `../mcp_server/lib/*` and exits non-zero on any
difference. This is the safety net that makes duplication acceptable — the two
copies are provably identical or the check fails.

### 5. Ripple to consumers

- `boukensha.gemspec` (steps 10/11/12) already depends only on
  `mud_manager_mcp`, not on `mcp_server` — **no change**. Fewer transitive gems
  is strictly simpler for them.
- `Tools::MudMcp` spawns `bin/mud_manager_mcp` as a subprocess and never loads
  `mcp_server` itself — **no change**.
- Rebuild/reinstall order collapses from three gems to two:
  `mud_manager_mcp` then `boukensha` (was: `mcp_server`, `mud_manager_mcp`,
  `boukensha`). Update the three step READMEs' "Building the gem" blocks
  accordingly.

---

## Compatibility

- `bin/mud_manager_mcp`'s public behaviour is unchanged — same flags, same env
  vars, same 31 tools, same protocol. Only where the transport *comes from*
  changes.
- The standalone `mcp_server` gem and `python/mcp_server/` are untouched under
  Approach A; anyone already using them is unaffected.
- The step gems keep working with no edits beyond the README build instructions.

---

## Verification

1. `gem build mud_manager_mcp.gemspec` with **no `mcp_server` installed** and
   **no sibling checkout on `$LOAD_PATH`**; `gem install` the result; confirm it
   installs with zero dependencies (`gem dependency mud_manager_mcp` lists
   none).
2. Run `bin/mud_manager_mcp` from that installed gem alone: handshake →
   `mud-manager vX`, `tools/list` → 31 tools, a live `look` → room name.
3. The vendor-diff task passes (copies identical to canonical).
4. Full step regression, both languages: MUD over MCP 31 tools, in-process 27,
   live `look` on both — steps 10, 11, 12 still green.
5. Installed `boukensha` binary still boots and reaches the MUD, now with one
   fewer gem in the chain.

---

## Decisions needed before starting

1. **Which approach** — (A) vendor + keep standalone gem [recommended], (B)
   absorb + delete standalone, (C) rejected?
2. **If (A): where do the vendored files live** — `lib/vendor/mcp_server*`
   [recommended] or somewhere else — and do we keep the `McpServer` module name
   (recommended, no code churn) or re-namespace under `MudManagerMcp`?
3. **Drift guard** — add the diff verify task now, or accept manual re-copy
   discipline?
4. **`week0_explore/mud_manager`** — leave the stale original as-is, or delete
   it as part of the cleanup (it is unrelated to shipping but adds to the "why
   are there three mud_managers" confusion)?

## Not in scope

- The Python side. `python/mcp_server/` and `python/mud_manager/` are separate
  packages that already run without an install step (added to `sys.path`), so
  they have no "two gems to install" problem. If desired, a symmetric Python
  cleanup can be a follow-up.
- Merging the in-process `tools/mud.*` fallback away — kept deliberately as the
  no-subprocess path (see `generic_mcp_server.md` "Not in scope").
- Any change to the wire protocol, the tool set, or session handling.
