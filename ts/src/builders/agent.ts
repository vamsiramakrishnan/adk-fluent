/**
 * Agent builder — fluent wrapper around @google/adk LlmAgent.
 *
 * Usage:
 *   const agent = new Agent("helper", "gemini-2.5-flash")
 *     .instruct("You are a helpful assistant.")
 *     .tool(searchFn)
 *     .build();
 */

import { BuilderBase, autoBuild } from "../core/builder-base.js";
import type { CallbackFn, ToolFn } from "../core/types.js";

/**
 * Fluent builder for LLM-backed agents.
 *
 * Every setter returns a new immutable builder instance.
 * Call `.build()` to produce a native `LlmAgent` from `@google/adk`.
 */
export class Agent extends BuilderBase {
  constructor(name: string, model?: string) {
    super(name);
    if (model) {
      this._config.set("model", model);
    }
  }

  // ------------------------------------------------------------------
  // Core configuration
  // ------------------------------------------------------------------

  /** Set the LLM model (e.g., "gemini-2.5-flash"). */
  model(model: string): this {
    return this._setConfig("model", model);
  }

  /**
   * Set the main instruction / system prompt.
   * This is what the LLM is told to do.
   */
  instruct(instruction: string | ((...args: unknown[]) => string)): this {
    return this._setConfig("instruction", instruction);
  }

  /**
   * Set agent description (metadata for transfer routing and topology).
   * NOT sent to the LLM as instruction.
   */
  describe(description: string): this {
    return this._setConfig("description", description);
  }

  /**
   * Set cached instruction. When set, .instruct() text moves from system
   * to user content, enabling context caching. Use for large, stable sections.
   */
  static_(cachedInstruction: string): this {
    return this._setConfig("static_instruction", cachedInstruction);
  }

  /**
   * Set instruction shared by ALL agents in a workflow.
   * Only meaningful on the root agent.
   */
  globalInstruct(instruction: string): this {
    return this._setConfig("global_instruction", instruction);
  }

  // ------------------------------------------------------------------
  // Tools
  // ------------------------------------------------------------------

  /** Add a single tool function. */
  tool(fn: ToolFn): this {
    return this._addToList("tools", fn);
  }

  /** Set/replace all tools at once. */
  tools(toolList: ToolFn[]): this {
    return this._setList("tools", toolList);
  }

  /**
   * Wrap another agent as a callable AgentTool.
   * The parent LLM invokes the child like any other tool and stays in control.
   */
  agentTool(agent: BuilderBase | unknown): this {
    return this._addToList("tools", { type: "agent_tool", agent });
  }

  // ------------------------------------------------------------------
  // Sub-agents (transfer control)
  // ------------------------------------------------------------------

  /**
   * Add a child agent as a transfer target.
   * The LLM decides when to hand off via transfer_to_agent.
   */
  subAgent(agent: BuilderBase | unknown): this {
    return this._addToList("sub_agents", agent);
  }

  /**
   * Prevent transfers to parent AND peers.
   * Agent completes its task, then control auto-returns to parent.
   */
  isolate(): this {
    return this._setConfig("disallow_transfer_to_parent", true)
      ._setConfig("disallow_transfer_to_peers", true);
  }

  /** Prevent transfer to parent only (can still transfer to siblings). */
  stay(): this {
    return this._setConfig("disallow_transfer_to_parent", true);
  }

  /** Prevent transfer to siblings only (can still return to parent). */
  noPeers(): this {
    return this._setConfig("disallow_transfer_to_peers", true);
  }

  // ------------------------------------------------------------------
  // Data flow
  // ------------------------------------------------------------------

  /**
   * Constrain LLM response to structured JSON matching a schema.
   * In TypeScript, pass a Zod schema.
   */
  returns(schema: unknown): this {
    return this._setConfig("_output_schema", schema);
  }

  /** Validate input when this agent is invoked as a tool. */
  accepts(schema: unknown): this {
    return this._setConfig("_input_schema", schema);
  }

  // ------------------------------------------------------------------
  // Callbacks
  // ------------------------------------------------------------------

  /** Run before agent executes. */
  beforeAgent(fn: CallbackFn): this {
    return this._addCallback("before_agent_callback", fn);
  }

  /** Run after agent executes. */
  afterAgent(fn: CallbackFn): this {
    return this._addCallback("after_agent_callback", fn);
  }

  /** Run before LLM call. */
  beforeModel(fn: CallbackFn): this {
    return this._addCallback("before_model_callback", fn);
  }

  /** Run after LLM call. */
  afterModel(fn: CallbackFn): this {
    return this._addCallback("after_model_callback", fn);
  }

  /** Run before tool call. */
  beforeTool(fn: CallbackFn): this {
    return this._addCallback("before_tool_callback", fn);
  }

  /** Run after tool call. */
  afterTool(fn: CallbackFn): this {
    return this._addCallback("after_tool_callback", fn);
  }

  // ------------------------------------------------------------------
  // Guard
  // ------------------------------------------------------------------

  /** Output validation guard (after_model). */
  guard(fn: CallbackFn): this {
    return this._addCallback("after_model_callback", fn);
  }

  // ------------------------------------------------------------------
  // Configuration
  // ------------------------------------------------------------------

  /** Model-level config (temperature, top_p, etc.). */
  generateContentConfig(config: Record<string, unknown>): this {
    return this._setConfig("generate_content_config", config);
  }

  // ------------------------------------------------------------------
  // Build
  // ------------------------------------------------------------------

  /**
   * Produce a native `LlmAgent` from `@google/adk`.
   *
   * This method attempts to import from @google/adk. If the package is not
   * installed, it returns a plain config object for testing/inspection.
   */
  build(): unknown {
    const config: Record<string, unknown> = {};

    // Map config keys to LlmAgent constructor args
    for (const [k, v] of this._config) {
      if (!k.startsWith("_")) {
        config[k] = v;
      }
    }

    // Resolve tool list
    const tools = this._lists.get("tools");
    if (tools && tools.length > 0) {
      config.tools = tools;
    }

    // Resolve sub-agents
    const subAgents = this._lists.get("sub_agents");
    if (subAgents && subAgents.length > 0) {
      config.subAgents = subAgents.map((sa) => autoBuild(sa as BuilderBase));
    }

    // Resolve callbacks
    for (const [cbKey, fns] of this._callbacks) {
      if (fns.length === 1) {
        config[cbKey] = fns[0];
      } else if (fns.length > 1) {
        // Compose multiple callbacks into one
        config[cbKey] = async (...args: unknown[]) => {
          for (const fn of fns) {
            await fn(...args);
          }
        };
      }
    }

    // Handle output schema
    const outputSchema = this._config.get("_output_schema");
    if (outputSchema) {
      config.outputSchema = outputSchema;
    }

    // Return a plain config object. Real @google/adk wiring happens via the
    // codegen pipeline (or via .native() hooks) — keeping build() synchronous
    // and side-effect-free makes the builder safe to use in tests and ESM.
    const result: Record<string, unknown> = { _type: "LlmAgent", ...config };

    const nativeHooks = this._callbacks.get("_native_hooks");
    if (nativeHooks) {
      for (const hook of nativeHooks) {
        hook(result);
      }
    }

    return result;
  }
}
