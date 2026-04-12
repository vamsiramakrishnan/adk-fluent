/**
 * Tests for BuilderBase immutable builder pattern.
 */
import { describe, expect, it } from "vitest";
import { Agent } from "../../src/builders/agent.js";
import { Pipeline, FanOut, Loop, Fallback } from "../../src/builders/workflow.js";

describe("Agent builder", () => {
  it("creates an agent with name and model", () => {
    const agent = new Agent("helper", "gemini-2.5-flash");
    expect(agent.name).toBe("helper");
    const config = agent.inspect();
    expect(config.model).toBe("gemini-2.5-flash");
  });

  it("sets instruction via .instruct()", () => {
    const agent = new Agent("helper").instruct("Be helpful.");
    const config = agent.inspect();
    expect(config.instruction).toBe("Be helpful.");
  });

  it("is immutable — .instruct() returns a new instance", () => {
    const a = new Agent("helper");
    const b = a.instruct("Be helpful.");
    expect(a.inspect().instruction).toBeUndefined();
    expect(b.inspect().instruction).toBe("Be helpful.");
  });

  it("chains multiple setters", () => {
    const agent = new Agent("helper", "gemini-2.5-flash")
      .instruct("Be helpful.")
      .describe("A helper agent")
      .writes("result");

    const config = agent.inspect();
    expect(config.model).toBe("gemini-2.5-flash");
    expect(config.instruction).toBe("Be helpful.");
    expect(config.description).toBe("A helper agent");
    expect(config.output_key).toBe("result");
  });

  it("adds tools via .tool()", () => {
    const fn = () => "result";
    const agent = new Agent("helper").tool(fn);
    const config = agent.inspect();
    expect(config["lists.tools"]).toBe(1);
  });

  it("builds to a config object", () => {
    const result = new Agent("helper", "gemini-2.5-flash")
      .instruct("Be helpful.")
      .build() as Record<string, unknown>;
    expect(result._type).toBe("LlmAgent");
    expect(result.name).toBe("helper");
    expect(result.model).toBe("gemini-2.5-flash");
    expect(result.instruction).toBe("Be helpful.");
  });

  it("supports .isolate() for transfer control", () => {
    const agent = new Agent("specialist").isolate();
    const config = agent.inspect();
    expect(config.disallow_transfer_to_parent).toBe(true);
    expect(config.disallow_transfer_to_peers).toBe(true);
  });
});

describe("Pipeline builder", () => {
  it("creates a pipeline with steps", () => {
    const pipeline = new Pipeline("flow")
      .step(new Agent("a").instruct("Step 1"))
      .step(new Agent("b").instruct("Step 2"));

    expect(pipeline.name).toBe("flow");
    const config = pipeline.inspect();
    expect(config["lists.sub_agents"]).toBe(2);
  });

  it("builds to a SequentialAgent config", () => {
    const result = new Pipeline("flow")
      .step(new Agent("a").instruct("Step 1"))
      .step(new Agent("b").instruct("Step 2"))
      .build() as Record<string, unknown>;

    expect(result._type).toBe("SequentialAgent");
    expect(result.name).toBe("flow");
    expect(Array.isArray(result.subAgents)).toBe(true);
    expect((result.subAgents as unknown[]).length).toBe(2);
  });
});

describe("FanOut builder", () => {
  it("creates parallel branches", () => {
    const fanout = new FanOut("parallel")
      .branch(new Agent("web").instruct("Search web"))
      .branch(new Agent("papers").instruct("Search papers"));

    expect(fanout.name).toBe("parallel");
    const config = fanout.inspect();
    expect(config["lists.sub_agents"]).toBe(2);
  });

  it("builds to a ParallelAgent config", () => {
    const result = new FanOut("parallel")
      .branch(new Agent("a"))
      .branch(new Agent("b"))
      .build() as Record<string, unknown>;

    expect(result._type).toBe("ParallelAgent");
    expect((result.subAgents as unknown[]).length).toBe(2);
  });
});

describe("Loop builder", () => {
  it("creates a loop with max iterations", () => {
    const loop = new Loop("refine")
      .step(new Agent("writer").instruct("Write"))
      .step(new Agent("critic").instruct("Critique"))
      .maxIterations(3);

    expect(loop.name).toBe("refine");
    const config = loop.inspect();
    expect(config.max_iterations).toBe(3);
    expect(config["lists.sub_agents"]).toBe(2);
  });

  it("builds to a LoopAgent config", () => {
    const result = new Loop("refine")
      .step(new Agent("a"))
      .maxIterations(5)
      .build() as Record<string, unknown>;

    expect(result._type).toBe("LoopAgent");
    expect(result.maxIterations).toBe(5);
  });
});

describe("Composition methods", () => {
  it(".then() creates a Pipeline", () => {
    const a = new Agent("a");
    const b = new Agent("b");
    const result = a.then(b);
    expect(result).toBeInstanceOf(Pipeline);
  });

  it(".parallel() creates a FanOut", () => {
    const a = new Agent("a");
    const b = new Agent("b");
    const result = a.parallel(b);
    expect(result).toBeInstanceOf(FanOut);
  });

  it(".times() creates a Loop", () => {
    const a = new Agent("a");
    const result = a.times(3);
    expect(result).toBeInstanceOf(Loop);
  });

  it(".fallback() creates a Fallback", () => {
    const a = new Agent("fast");
    const b = new Agent("strong");
    const result = a.fallback(b);
    expect(result).toBeInstanceOf(Fallback);
  });

  it(".then() chaining produces multi-step pipeline", () => {
    const result = new Agent("a").then(new Agent("b")).then(new Agent("c"));
    expect(result).toBeInstanceOf(Pipeline);
    const config = result.inspect();
    // Should have 3 sub-agents (a, b, c)
    expect(config["lists.sub_agents"]).toBe(3);
  });

  it(".timesUntil() creates conditional loop", () => {
    const pred = (s: Record<string, unknown>) => s["done"] === true;
    const result = new Agent("a").timesUntil(pred, { max: 5 });
    expect(result).toBeInstanceOf(Loop);
    const config = result.inspect();
    expect(config.max_iterations).toBe(5);
    expect(config._until_predicate).toBe(pred);
  });
});

describe("Fallback builder", () => {
  it("adds alternatives via .attempt()", () => {
    const fb = new Fallback("resilient")
      .attempt(new Agent("fast"))
      .attempt(new Agent("strong"));

    const result = fb.build() as Record<string, unknown>;
    expect(result._type).toBe("Fallback");
    expect((result.children as unknown[]).length).toBe(2);
  });
});
