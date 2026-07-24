# Vendored code — do not edit here

These files are **byte-identical copies** of the standalone
[`mcp_server`](../../../mcp_server) gem's `lib/`:

| Vendored | Canonical source |
| --- | --- |
| `mcp_server.rb` | `../../mcp_server/lib/mcp_server.rb` |
| `mcp_server/server.rb` | `../../mcp_server/lib/mcp_server/server.rb` |
| `mcp_server/tool_table.rb` | `../../mcp_server/lib/mcp_server/tool_table.rb` |

## Why vendored

`mud_manager_mcp` ships as a **single self-contained gem** — `gem install
mud_manager_mcp` pulls no other gems and `bin/mud_manager_mcp` runs from this
one gem alone. The generic MCP transport that makes that work lives in its own
reusable gem (`mcp_server`, still the canonical source and the "write your own
server" teaching artifact); this is a copy so the MUD server carries it without
a runtime dependency.

## Editing rule

**Never edit these copies.** Change `../../mcp_server/lib/*` and re-copy:

```sh
cp ../../mcp_server/lib/mcp_server.rb            mcp_server.rb
cp ../../mcp_server/lib/mcp_server/server.rb     mcp_server/server.rb
cp ../../mcp_server/lib/mcp_server/tool_table.rb mcp_server/tool_table.rb
```

`ruby tasks/verify_vendor.rb` (from the gem root) diffs the two and fails if
they have drifted, so a stale copy is caught rather than silently shipped.
