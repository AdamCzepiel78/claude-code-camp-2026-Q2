#!/usr/bin/env ruby
# frozen_string_literal: true
#
# Verify that the vendored McpServer transport (lib/vendor) is byte-identical to
# its canonical source, the standalone mcp_server gem. Run from a checkout:
#
#   ruby tasks/verify_vendor.rb
#
# Exits 0 when the copies match, 1 on any drift or a missing canonical source.
# This is the safety net that makes vendoring acceptable — a stale copy is
# caught here rather than silently shipped. It is a dev-time check: the
# canonical sibling directory is not present in the installed gem, and does not
# need to be.

require "fileutils"

GEM_ROOT  = File.expand_path("..", __dir__)
VENDOR    = File.join(GEM_ROOT, "lib", "vendor")
CANONICAL = File.expand_path("../mcp_server/lib", GEM_ROOT)  # sibling checkout

PAIRS = {
  "mcp_server.rb"            => "mcp_server.rb",
  "mcp_server/server.rb"     => "mcp_server/server.rb",
  "mcp_server/tool_table.rb" => "mcp_server/tool_table.rb"
}

unless File.directory?(CANONICAL)
  warn "verify_vendor: canonical source not found at #{CANONICAL}"
  warn "  (run this from a checkout where week1_baseline/mcp_server is a sibling)"
  exit 1
end

drifted = PAIRS.reject do |vendored, canonical|
  a = File.join(VENDOR, vendored)
  b = File.join(CANONICAL, canonical)
  File.exist?(a) && File.exist?(b) && FileUtils.identical?(a, b)
end

if drifted.empty?
  puts "verify_vendor: OK — #{PAIRS.size} vendored files identical to mcp_server"
  exit 0
end

warn "verify_vendor: DRIFT — these copies differ from the canonical source:"
drifted.each_key { |v| warn "  lib/vendor/#{v}" }
warn "Re-copy from ../mcp_server/lib (see lib/vendor/README.md)."
exit 1
