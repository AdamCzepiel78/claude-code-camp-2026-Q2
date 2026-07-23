require "json"
require_relative "base"

# Mammouth AI backend — OpenAI-compatible.
#
# Mammouth (https://mammouth.ai) fronts every major model family — Claude, GPT,
# Gemini, DeepSeek, Qwen, Mistral, Grok, Kimi — behind a single OpenAI-compatible
# Chat Completions API. This backend therefore mirrors openai.rb exactly (same
# message/tool serialization, the same normalized parse_response, and the same
# assistant_message rebuild) and differs only in its base URL, its multi-family
# model table, and the payload's token-limit field: Mammouth expects max_tokens,
# not OpenAI's newer max_completion_tokens.
module Boukensha
  module Backends
    class Mammouth < Base
      BASE_URL = "https://api.mammouth.ai/v1/chat/completions"
      MODELS = {
        "claude-sonnet-5" => {
          context_window: 1_000_000,
          cost_per_million: { input: 2.0, output: 10.0 },
          usage_unit: :tokens
        },
        "claude-opus-4-8" => {
          context_window: 1_000_000,
          cost_per_million: { input: 5.0, output: 25.0 },
          usage_unit: :tokens
        },
        "claude-sonnet-4" => {
          context_window: 1_000_000,
          cost_per_million: { input: 3.0, output: 15.0 },
          usage_unit: :tokens
        },
        "claude-haiku-4-5" => {
          context_window: 1_000_000,
          cost_per_million: { input: 1.0, output: 5.0 },
          usage_unit: :tokens
        },
        "claude-sonnet-4-5" => {
          context_window: 1_000_000,
          cost_per_million: { input: 3.0, output: 15.0 },
          usage_unit: :tokens
        },
        "claude-sonnet-4-6" => {
          context_window: 1_000_000,
          cost_per_million: { input: 3.0, output: 15.0 },
          usage_unit: :tokens
        },
        "gpt-5.5" => {
          context_window: 1_050_000,
          cost_per_million: { input: 5.0, output: 30.0 },
          usage_unit: :tokens
        },
        "gpt-5.4" => {
          context_window: 922_000,
          cost_per_million: { input: 2.5, output: 15.0 },
          usage_unit: :tokens
        },
        "gemini-3.5-flash" => {
          context_window: 1_048_576,
          cost_per_million: { input: 1.5, output: 9.0 },
          usage_unit: :tokens
        },
        "gemini-2.5-pro" => {
          context_window: 1_048_576,
          cost_per_million: { input: 2.5, output: 15.0 },
          usage_unit: :tokens
        },
        "mistral-large-3" => {
          context_window: 262_144,
          cost_per_million: { input: 0.5, output: 1.5 },
          usage_unit: :tokens
        },
        "grok-4.5" => {
          context_window: 500_000,
          cost_per_million: { input: 2.0, output: 6.0 },
          usage_unit: :tokens
        },
        "deepseek-v4-pro" => {
          context_window: 1_050_000,
          cost_per_million: { input: 1.74, output: 3.48 },
          usage_unit: :tokens
        },
        "qwen3.7-max" => {
          context_window: 1_000_000,
          cost_per_million: { input: 2.5, output: 7.5 },
          usage_unit: :tokens
        },
        "kimi-k3" => {
          context_window: 1_048_576,
          cost_per_million: { input: 3.0, output: 15.0 },
          usage_unit: :tokens
        },
        "mammouth-recommended" => {
          context_window: 1_048_576,
          cost_per_million: { input: 1.4, output: 4.4 },
          usage_unit: :tokens
        }
      }.freeze

      def initialize(api_key:, model:)
        @api_key = api_key
        configure_model(model)
      end

      def to_messages(system, messages)
        system_message = [{ role: "system", content: system }]
        conversation   = messages.map do |msg|
          case msg.role
          when :tool_result
            { role: "tool", tool_call_id: msg.tool_use_id, content: msg.content }
          when :assistant
            assistant_message(msg.content)
          else
            { role: msg.role.to_s, content: msg.content }
          end
        end
        system_message + conversation
      end

      def to_tools(tools)
        tools.values.map do |tool|
          {
            type: "function",
            function: {
              name: tool.name,
              description: tool.description,
              parameters: {
                type: "object",
                properties: tool.parameters,
                required: tool.parameters.keys.map(&:to_s)
              }
            }
          }
        end
      end

      def to_payload(context, max_output_tokens: 1024, tools: nil)
        {
          model: @model,
          messages: to_messages(context.system, context.messages),
          tools: tools.nil? ? to_tools(context.tools) : tools,
          max_tokens: max_output_tokens
        }
      end

      def headers
        {
          "Content-Type"  => "application/json",
          "Authorization" => "Bearer #{@api_key}"
        }
      end

      def url
        BASE_URL
      end

      # Normalizes a Mammouth (OpenAI-compatible) chat completions response into
      # the common shape:
      #   { stop_reason: "tool_use" | "end_turn", content: [ {"type"=>"text", "text"=>...} | {"type"=>"tool_use", "id"=>, "name"=>, "input"=>} ] }
      def parse_response(response)
        message    = response.dig("choices", 0, "message") || {}
        tool_calls = message["tool_calls"] || []

        content = []
        content << { "type" => "text", "text" => message["content"] } if message["content"]

        tool_calls.each do |tc|
          content << {
            "type"  => "tool_use",
            "id"    => tc["id"],
            "name"  => tc.dig("function", "name"),
            "input" => JSON.parse(tc.dig("function", "arguments") || "{}")
          }
        end

        { stop_reason: tool_calls.empty? ? "end_turn" : "tool_use", content: content }
      end

      private

      # Rebuilds a Mammouth (OpenAI-compatible) assistant message from normalized
      # content blocks (the inverse of parse_response).
      def assistant_message(content)
        blocks = content.is_a?(String) ? [{ "type" => "text", "text" => content }] : content

        text_blocks = blocks.select { |b| b["type"] == "text" }
        tool_blocks = blocks.select { |b| b["type"] == "tool_use" }

        message = { role: "assistant", content: text_blocks.map { |b| b["text"] }.join }
        unless tool_blocks.empty?
          message[:tool_calls] = tool_blocks.map do |b|
            {
              id: b["id"],
              type: "function",
              function: { name: b["name"], arguments: b["input"].to_json }
            }
          end
        end
        message
      end
    end
  end
end
