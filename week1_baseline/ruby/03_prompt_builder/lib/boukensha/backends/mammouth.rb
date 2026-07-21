require_relative "base"

# Mammouth AI backend — OpenAI-compatible.
#
# Mammouth (https://mammouth.ai) exposes an OpenAI-compatible Chat Completions
# API, so this backend mirrors openai.rb exactly except for its base URL, its
# model table, and the payload's token-limit field (max_tokens, per Mammouth's
# API docs) instead of OpenAI's newer max_completion_tokens.
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

      def to_payload(context, max_output_tokens: 1024)
        {
          model: @model,
          messages: to_messages(context.system, context.messages),
          tools: to_tools(context.tools),
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
    end
  end
end
