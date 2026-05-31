/**
 * Tests for AdkSubagentRunner — the real ADK-backed subagent runner ported
 * from Python's `adk_fluent._subagents._adk_runner` (Feature #1) plus the
 * context-threading fix (#22).
 *
 * No real LLM is invoked: `@google/adk`'s `InMemoryRunner` is mocked so
 * `runEphemeral` becomes a spy that yields a canned event and captures the
 * `stateDelta` it was handed — mirroring how the Python test monkeypatches the
 * `_adk_run_once` seam to assert the caller's `context` is threaded into the
 * fresh session's state.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// --- Mock the ADK runtime seam ------------------------------------------
// Captures every runEphemeral() call so tests can assert the threaded state.
const ephemeralCalls: Array<{
  userId: string;
  newMessage: unknown;
  stateDelta: Record<string, unknown> | undefined;
  appName: string;
}> = [];

// What the mocked runner should "produce" as the agent's last text. A holder
// object lets individual tests swap the behavior (success vs. thrown error).
const runnerBehavior: {
  output: string;
  throwError?: Error;
} = { output: "" };

vi.mock("@google/adk", () => {
  class InMemoryRunner {
    private readonly appName: string;
    constructor(input: { agent: unknown; appName?: string }) {
      this.appName = input.appName ?? "";
    }
    async *runEphemeral(params: {
      userId: string;
      newMessage: unknown;
      stateDelta?: Record<string, unknown>;
    }): AsyncGenerator<unknown, void, undefined> {
      ephemeralCalls.push({
        userId: params.userId,
        newMessage: params.newMessage,
        stateDelta: params.stateDelta,
        appName: this.appName,
      });
      if (runnerBehavior.throwError) {
        throw runnerBehavior.throwError;
      }
      yield {
        content: { parts: [{ text: runnerBehavior.output }] },
      };
    }
  }
  return { InMemoryRunner };
});

// Importing the workflow builders wires the workflow-builder registry as a
// side effect, so the runner's default-build path (real `Agent`) can
// `.build()` without the package barrel (which would re-pull the mocked ADK).
import "../../src/builders/workflow.js";
import {
  AdkSubagentRunner,
  SubagentSpec,
  SubagentRegistry,
  SubagentResult,
  SubagentRunnerError,
  makeTaskTool,
} from "../../src/namespaces/harness/subagents.js";

/** Minimal mocked fluent-agent builder for the agentFactory escape hatch. */
function fakeAgentBuilder(name: string) {
  const toolsAttached: unknown[] = [];
  const builder = {
    instruct: () => builder,
    describe: () => builder,
    tool: (t: unknown) => {
      toolsAttached.push(t);
      return builder;
    },
    build: () => ({ name }),
    toolsAttached,
  };
  return builder;
}

describe("AdkSubagentRunner", () => {
  beforeEach(() => {
    ephemeralCalls.length = 0;
    runnerBehavior.output = "";
    runnerBehavior.throwError = undefined;
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("runs a spec and returns a non-error result with output", async () => {
    runnerBehavior.output = "three papers found";
    const runner = new AdkSubagentRunner({
      agentFactory: (spec) => fakeAgentBuilder(spec.role),
    });
    const spec = new SubagentSpec({
      role: "researcher",
      instruction: "Find three papers.",
      description: "Deep research",
    });

    const result = await runner.runAsync(spec, "go research");

    expect(result).toBeInstanceOf(SubagentResult);
    expect(result.isError).toBe(false);
    expect(result.error).toBe("");
    expect(result.role).toBe("researcher");
    expect(result.output).toBe("three papers found");
    expect(ephemeralCalls).toHaveLength(1);
    expect(ephemeralCalls[0].appName).toBe("subagent_researcher");
  });

  it("threads the supplied context into the run as session state (#22)", async () => {
    runnerBehavior.output = "ok";
    const runner = new AdkSubagentRunner({
      agentFactory: (spec) => fakeAgentBuilder(spec.role),
    });
    const spec = new SubagentSpec({
      role: "reviewer",
      instruction: "Critique the draft.",
    });
    const context = { draft: "v1", owner: "alice" };

    const result = await runner.runAsync(spec, "review it", context);

    expect(result.isError).toBe(false);
    // The key #22 assertion: context is threaded into the ephemeral session's
    // initial state and is NOT dropped.
    expect(ephemeralCalls).toHaveLength(1);
    expect(ephemeralCalls[0].stateDelta).toEqual(context);
    // The prompt is delivered as the user message.
    expect(ephemeralCalls[0].newMessage).toEqual({
      role: "user",
      parts: [{ text: "review it" }],
    });
  });

  it("maps a thrown execution error to an error result", async () => {
    runnerBehavior.throwError = new Error("model exploded");
    const runner = new AdkSubagentRunner({
      agentFactory: (spec) => fakeAgentBuilder(spec.role),
    });
    const spec = new SubagentSpec({
      role: "researcher",
      instruction: "Find papers.",
    });

    const result = await runner.runAsync(spec, "go");

    expect(result.isError).toBe(true);
    expect(result.error).toContain("model exploded");
    expect(result.output).toBe("");
    expect(result.role).toBe("researcher");
  });

  it("resolves tool names via the resolver and skips unresolved ones", async () => {
    runnerBehavior.output = "done";
    const resolved: string[] = [];
    // No agentFactory → exercise the real default-build path so the resolver
    // is actually consulted while building the fluent Agent.
    const runner = new AdkSubagentRunner({
      toolResolver: (name) => {
        resolved.push(name);
        if (name === "missing") return undefined;
        if (name === "boom") throw new Error("bad resolver");
        return { name };
      },
    });
    const spec = new SubagentSpec({
      role: "tooluser",
      instruction: "Use tools.",
      toolNames: ["search", "missing", "boom"],
    });

    const result = await runner.runAsync(spec, "work");

    expect(result.isError).toBe(false);
    // All three names were attempted; "missing" and "boom" skipped gracefully.
    expect(resolved).toEqual(["search", "missing", "boom"]);
  });

  it("synchronous run() throws directing callers to runAsync", () => {
    const runner = new AdkSubagentRunner({
      agentFactory: (spec) => fakeAgentBuilder(spec.role),
    });
    const spec = new SubagentSpec({
      role: "researcher",
      instruction: "Find papers.",
    });
    expect(() => runner.run(spec, "go")).toThrowError(SubagentRunnerError);
    expect(() => runner.run(spec, "go")).toThrow(/runAsync/);
  });

  it("wires up via makeTaskTool(registry, new AdkSubagentRunner())", () => {
    const registry = new SubagentRegistry([
      new SubagentSpec({
        role: "researcher",
        instruction: "Find three papers.",
        description: "Deep research",
      }),
    ]);
    const task = makeTaskTool(registry, new AdkSubagentRunner());

    expect(typeof task).toBe("function");
    expect(task.toolName).toBe("task");
    expect(task.description).toContain("researcher");

    // Calling the sync task tool surfaces the sync-run guard gracefully as an
    // error string rather than throwing (makeTaskTool catches runner errors).
    const out = task("researcher", "go");
    expect(out).toContain("[researcher:error]");
    expect(out).toContain("runAsync");
  });
});
