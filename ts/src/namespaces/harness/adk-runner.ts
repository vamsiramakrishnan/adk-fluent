/**
 * AdkSubagentRunner — a real runner that executes a spec via the ADK engine.
 *
 * `FakeSubagentRunner` is great for tests and canned-response sandboxes, but
 * production callers need a runner that actually turns a `SubagentSpec` into a
 * running model. This module provides that: `AdkSubagentRunner` builds a
 * fluent `Agent` from the spec, executes it on the per-call prompt through the
 * same one-shot machinery the package uses (a `@google/adk` `InMemoryRunner`
 * driving a fresh ephemeral session), and folds the text response into a
 * `SubagentResult`.
 *
 * Parity notes (Python `adk_fluent._subagents._adk_runner`):
 *
 * - The Python runner threads the caller-supplied `context` into the fresh
 *   ADK session's initial state via `create_session(state=context)`. The TS
 *   one-shot seam is `Runner.runEphemeral({ stateDelta })`, so we pass
 *   `context` through as the ephemeral session's `stateDelta`. This is the
 *   context-threading fix (#22): the subagent must *see* the parent context
 *   during its run, never have it dropped.
 * - Python implements both `run` (sync) and `run_async`. JavaScript cannot
 *   block on a promise, so the genuine execution path is async (`runAsync`).
 *   The synchronous `run` required by the `SubagentRunner` interface throws a
 *   `SubagentRunnerError` directing callers to `runAsync` — mirroring the way
 *   Python's `run` raises when called from inside a running event loop.
 */

import { Agent } from "../../builders/agent.js";
import {
  SubagentResult,
  SubagentRunnerError,
  type SubagentRunner,
  type SubagentSpec,
} from "./subagents.js";

/** Model used when a spec does not pin its own `spec.model`. */
export const DEFAULT_MODEL = "gemini-2.5-flash";

/**
 * Minimal structural view of the fluent `Agent` builder this runner needs.
 *
 * Declared structurally (rather than importing the concrete `Agent` class) so
 * that an `agentFactory` may return any builder-compatible object — including
 * a mocked agent in tests — without dragging the full builder graph into this
 * module's type surface.
 */
export interface AgentBuilderLike {
  instruct(text: string): AgentBuilderLike;
  describe(text: string): AgentBuilderLike;
  tool(tool: unknown): AgentBuilderLike;
  build(): unknown;
}

/** Tool-name → tool resolver. Returning `undefined`/`null` skips the name. */
export type ToolResolver = (name: string) => unknown;

/** Escape hatch: fully build the fluent agent builder from a spec. */
export type AgentFactory = (spec: SubagentSpec) => AgentBuilderLike;

export interface AdkSubagentRunnerOptions {
  /**
   * Model used when a spec does not pin its own `spec.model`.
   * Defaults to {@link DEFAULT_MODEL}.
   */
  defaultModel?: string;
  /**
   * Optional callable mapping a tool name to a tool callable/object. When a
   * spec lists `toolNames` and a resolver is supplied, each name is resolved
   * and attached via `.tool()`. Names the resolver cannot resolve (returns
   * `undefined`/`null` or throws) are skipped gracefully rather than failing
   * the whole run.
   */
  toolResolver?: ToolResolver;
  /**
   * Escape hatch for advanced wiring. A callable `(spec) => Agent` that fully
   * builds the fluent `Agent` builder. When supplied, `defaultModel` and
   * `toolResolver` are ignored.
   */
  agentFactory?: AgentFactory;
}

/**
 * Execute a `SubagentSpec` as a real ADK agent.
 *
 * The runner is a thin orchestration layer over the fluent `Agent` builder and
 * the package's existing one-shot execution machinery — it deliberately does
 * *not* reimplement model invocation.
 */
export class AdkSubagentRunner implements SubagentRunner {
  private readonly defaultModel: string;
  private readonly toolResolver: ToolResolver | undefined;
  private readonly agentFactory: AgentFactory | undefined;

  constructor(options: AdkSubagentRunnerOptions = {}) {
    this.defaultModel = options.defaultModel ?? DEFAULT_MODEL;
    this.toolResolver = options.toolResolver;
    this.agentFactory = options.agentFactory;
  }

  // ------------------------------------------------------------------
  // Agent construction
  // ------------------------------------------------------------------

  /** Build a fluent `Agent` builder from `spec`. */
  private buildAgent(spec: SubagentSpec): AgentBuilderLike {
    if (this.agentFactory) {
      return this.agentFactory(spec);
    }

    let agent = new Agent(spec.role, spec.model ?? this.defaultModel)
      .instruct(spec.instruction)
      .describe(spec.description) as unknown as AgentBuilderLike;

    if (spec.toolNames.length > 0 && this.toolResolver) {
      for (const name of spec.toolNames) {
        let tool: unknown;
        try {
          tool = this.toolResolver(name);
        } catch {
          // A bad resolver must not abort the run — skip the name.
          tool = undefined;
        }
        if (tool != null) {
          agent = agent.tool(tool);
        }
      }
    }

    return agent;
  }

  // ------------------------------------------------------------------
  // Execution
  // ------------------------------------------------------------------

  /**
   * Async variant of {@link run}. Safe to `await`. Builds the agent, runs it
   * once on `prompt` through the ADK `InMemoryRunner`, and maps the result.
   *
   * Any `context` supplied by the caller (e.g. parent state threaded in by
   * `makeTaskTool(..., { contextProvider })`) seeds the fresh ADK session's
   * initial state via `runEphemeral({ stateDelta })`, so the subagent sees it
   * during the run — honoring the `SubagentRunner` contract that
   * `FakeSubagentRunner` also upholds.
   */
  async runAsync(
    spec: SubagentSpec,
    prompt: string,
    context?: Record<string, unknown>,
  ): Promise<SubagentResult> {
    try {
      const output = await this.execute(spec, prompt, context);
      return new SubagentResult({ role: spec.role, output });
    } catch (exc) {
      const reason = exc instanceof Error ? exc.message : String(exc);
      return new SubagentResult({ role: spec.role, output: "", error: reason });
    }
  }

  /** Build the agent and run it once on `prompt`; return the text. */
  private async execute(
    spec: SubagentSpec,
    prompt: string,
    context?: Record<string, unknown>,
  ): Promise<string> {
    // Lazy import of the ADK runtime so this module stays importable in
    // environments that only need the fake runner.
    const { InMemoryRunner } = await import("@google/adk");

    const builder = this.buildAgent(spec);
    const agent = builder.build();

    // App names must start with a letter; `spec.role` already does (the spec
    // rejects empty roles). The prefix keeps it unambiguous.
    const agentName = (agent as { name?: string } | undefined)?.name ?? spec.role;
    const appName = `subagent_${agentName}`;

    const runner = new InMemoryRunner({
      // The fluent builder's `.build()` is the package's native-agent seam.
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      agent: agent as any,
      appName,
    });

    const newMessage = { role: "user", parts: [{ text: prompt }] };

    let lastText = "";
    // `runEphemeral` runs the agent in a fresh, throwaway session and threads
    // `context` in as the initial state delta (the #22 fix).
    for await (const event of runner.runEphemeral({
      userId: "_ask_user",
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      newMessage: newMessage as any,
      stateDelta: context,
    })) {
      const parts = (event as { content?: { parts?: Array<{ text?: string }> } }).content?.parts;
      if (parts) {
        for (const part of parts) {
          if (typeof part.text === "string" && part.text.length > 0) {
            lastText = part.text;
          }
        }
      }
    }
    return lastText;
  }

  /**
   * Execute `spec` with `prompt` synchronously.
   *
   * Implements the `SubagentRunner` interface. JavaScript cannot block on a
   * promise, so real model invocation is only available via {@link runAsync}.
   * This method always throws `SubagentRunnerError` directing callers to
   * `runAsync` — the structural analogue of Python's `run()` refusing to run
   * inside an active event loop.
   */
  run(_spec: SubagentSpec, _prompt: string, _context?: Record<string, unknown>): SubagentResult {
    throw new SubagentRunnerError(
      "AdkSubagentRunner.run() is synchronous but ADK execution is async in " +
        "JavaScript. Await runner.runAsync(spec, prompt, context) instead.",
    );
  }
}
