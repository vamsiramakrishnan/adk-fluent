/**
 * Parity tests for the five Python 0.18 BuilderBase features ported to TS:
 *   1. fromNative()           — adopt a built @google/adk agent
 *   2. toDict() / fromDict()  — structural round-trip
 *   3. toYaml() / fromYaml()  — YAML round-trip (optional `yaml` package)
 *   4. consumes/produces + enforceContracts() — runtime contract gates
 *   5. then() cross-namespace algebra (C bound to adjacent agent; S/A as steps)
 *   6. proceedIf()            — gate that skips on falsy, propagates errors
 *
 * Agents are never actually run against an LLM — every assertion operates on
 * builder state, the build()-produced dict, or directly invokes the stored
 * callbacks with a fake callback-context. This mirrors the existing
 * operator-algebra.test.ts approach of inspecting structure, not behavior.
 */
import { describe, expect, it } from "vitest";
import { Agent, BaseAgent } from "../../src/builders/agent.js";
import { Pipeline, FanOut } from "../../src/builders/workflow.js";
import { BuilderBase, registerBuilderClass } from "../../src/core/builder-base.js";
import { S } from "../../src/namespaces/state.js";
import { C, CTransform } from "../../src/namespaces/context.js";
import { A } from "../../src/namespaces/artifacts.js";

// Ensure the Agent / BaseAgent classes are resolvable by fromDict/fromNative.
// builder-base attempts an eager best-effort registration on load, but the
// agent.ts ↔ builder-base.ts import cycle can race that registration, so we
// register explicitly here (idempotent). Production code wires this via
// index.ts in the same way.
registerBuilderClass("Agent", Agent);
registerBuilderClass("BaseAgent", BaseAgent);

const M = "gemini-2.5-flash";

/** Pull the callbacks of a given kind off a built LlmAgent dict. */
function callbacksOf(builder: BuilderBase, key: string): Array<(ctx: unknown) => unknown> {
  // Reach into the built dict, where _buildConfig surfaces composed callbacks.
  const built = builder.build() as Record<string, unknown>;
  const cb = built[key];
  if (cb == null) return [];
  return Array.isArray(cb) ? (cb as Array<(c: unknown) => unknown>) : [cb as (c: unknown) => unknown];
}

describe("1. fromNative()", () => {
  it("round-trips an Agent (name / model / instruction / description)", () => {
    const native = new Agent("helper", M)
      .instruct("Be helpful.")
      .describe("A helper")
      .build();

    const rebuilt = BuilderBase.fromNative(native);
    expect(rebuilt).toBeInstanceOf(Agent);
    const cfg = rebuilt.inspect();
    expect(cfg.name).toBe("helper");
    expect(cfg.model).toBe(M);
    expect(cfg.instruction).toBe("Be helpful.");
    expect(cfg.description).toBe("A helper");
  });

  it("recovers a Pipeline topology recursively", () => {
    const native = new Pipeline("flow")
      .step(new Agent("a", M).instruct("Step 1"))
      .step(new Agent("b", M).instruct("Step 2"))
      .build();

    const rebuilt = BuilderBase.fromNative(native);
    expect(rebuilt).toBeInstanceOf(Pipeline);
    expect(rebuilt.name).toBe("flow");
    expect(rebuilt.inspect()["lists.sub_agents"]).toBe(2);

    // Children are restored as Agent builders.
    const childNames = (rebuilt as unknown as { _lists: Map<string, unknown[]> })._lists
      .get("sub_agents")!
      .map((c) => (c as BuilderBase).name);
    expect(childNames).toEqual(["a", "b"]);
  });

  it("maps ParallelAgent → FanOut", () => {
    const native = new FanOut("par").branch(new Agent("x", M)).branch(new Agent("y", M)).build();
    const rebuilt = BuilderBase.fromNative(native);
    expect(rebuilt).toBeInstanceOf(FanOut);
    expect(rebuilt.inspect()["lists.sub_agents"]).toBe(2);
  });

  it("throws a clear error for an unsupported native type", () => {
    expect(() => BuilderBase.fromNative({ _type: "WatTool", name: "nope" })).toThrow(
      /unsupported native agent type|unknown builder type|has no/i,
    );
    expect(() => BuilderBase.fromNative(null)).toThrow(/expected a native ADK agent/i);
  });
});

describe("2. toDict() / fromDict()", () => {
  it("toDict() produces a tagged structural snapshot", () => {
    const agent = new Agent("helper", M).instruct("Hi").describe("d");
    const d = agent.toDict();
    expect(d._type).toBe("Agent");
    const config = d.config as Record<string, unknown>;
    expect(config.name).toBe("helper");
    expect(config.model).toBe(M);
    expect(config.instruction).toBe("Hi");
    expect(config.description).toBe("d");
  });

  it("round-trip is structural-stable (toDict ∘ fromDict ∘ toDict)", () => {
    const original = new Pipeline("flow")
      .step(new Agent("a", M).instruct("Step 1").writes("r"))
      .step(new Agent("b", M).instruct("Step 2 using {r}"));

    const dict1 = original.toDict();
    const revived = BuilderBase.fromDict(dict1);
    const dict2 = revived.toDict();

    expect(dict2).toEqual(dict1);
    expect(revived).toBeInstanceOf(Pipeline);
    expect(revived.inspect()["lists.sub_agents"]).toBe(2);
  });

  it("does NOT restore callables (documented limitation)", () => {
    const fn = (s: Record<string, unknown>) => s;
    const agent = new Agent("a", M).beforeAgent(fn);
    const d = agent.toDict();
    // Callback serialized to a name string, not a live function.
    const cbs = d.callbacks as Record<string, unknown[]>;
    expect(cbs.before_agent_callback?.every((x) => typeof x === "string")).toBe(true);
  });
});

describe("3. toYaml() / fromYaml()", () => {
  it("YAML round-trips structurally (yaml package present)", () => {
    const original = new Agent("helper", M).instruct("Hi").describe("d");
    const yamlStr = original.toYaml();
    expect(typeof yamlStr).toBe("string");
    const revived = BuilderBase.fromYaml(yamlStr);
    expect(revived).toBeInstanceOf(Agent);
    expect(revived.toDict()).toEqual(original.toDict());
  });
});

describe("4. consumes / produces + enforceContracts()", () => {
  it("consumes/produces alone are annotation-only (no runtime callbacks)", () => {
    const agent = new Agent("a", M).consumes({ fields: ["x"] }).produces({ fields: ["y"] });
    expect(callbacksOf(agent, "before_agent_callback")).toHaveLength(0);
    expect(callbacksOf(agent, "after_agent_callback")).toHaveLength(0);
  });

  it("enforceContracts before-callback throws on a missing consumed key", () => {
    const agent = new Agent("a", M).consumes({ fields: ["needed"] }).enforceContracts();
    const before = callbacksOf(agent, "before_agent_callback");
    expect(before.length).toBeGreaterThan(0);

    // State missing "needed" → throws.
    expect(() => before[0]({ state: {} })).toThrow(/contract violation.*consumes.*needed/i);
    // State has "needed" → no throw.
    expect(before[0]({ state: { needed: 1 } })).toBeUndefined();
  });

  it("enforceContracts after-callback throws on an unwritten produced key", () => {
    const agent = new Agent("a", M).produces({ fields: ["result"] }).enforceContracts();
    const after = callbacksOf(agent, "after_agent_callback");
    expect(after.length).toBeGreaterThan(0);

    expect(() => after[0]({ state: {} })).toThrow(/contract violation.*produces.*result/i);
    expect(after[0]({ state: { result: "ok" } })).toBeUndefined();
  });

  it("reads field names from a Zod-like schema (.shape)", () => {
    const zodLike = { shape: { alpha: {}, beta: {} } };
    const agent = new Agent("a", M).consumes(zodLike).enforceContracts({ produces: false });
    const before = callbacksOf(agent, "before_agent_callback");
    expect(() => before[0]({ state: { alpha: 1 } })).toThrow(/beta/);
  });
});

describe("5. then() cross-namespace operator algebra", () => {
  it("Agent.then(C) binds the context to that agent (not a new step)", () => {
    const agent = new Agent("a", M).instruct("hi");
    const result = agent.then(C.window(5));
    // Stays an Agent — context was bound, no pipeline created.
    expect(result).toBeInstanceOf(Agent);
    expect(result.inspect()["_context_spec"]).toBeInstanceOf(CTransform);
  });

  it("Pipeline.then(C) reconfigures the last Agent step", () => {
    const pipe = new Agent("a", M).then(new Agent("b", M));
    const result = pipe.then(C.window(3));
    expect(result).toBeInstanceOf(Pipeline);
    const steps = (result as unknown as { _lists: Map<string, unknown[]> })._lists.get(
      "sub_agents",
    )!;
    // Last step is still an Agent, now carrying the context spec.
    const last = steps[steps.length - 1] as BuilderBase;
    expect(last).toBeInstanceOf(Agent);
    expect(last.inspect()["_context_spec"]).toBeInstanceOf(CTransform);
  });

  it("FanOut.then(C) throws — no Agent to receive the context", () => {
    const fan = new Agent("a", M).parallel(new Agent("b", M));
    expect(() => fan.then(C.window(5))).toThrow(/no Agent to receive/i);
  });

  it("mixed chain S → agent → C → A → agent builds one pipeline with C bound to adjacent agent", () => {
    const agent1 = new Agent("writer", M).instruct("write");
    const agent2 = new Agent("editor", M).instruct("edit");

    // S and A transforms become pipeline steps (wrapped like a plain fn-step);
    // the C transform binds to the adjacent agent's .context() instead of
    // adding a step. (The chain head is a builder because, per the edit
    // constraints, only builder-base/context were taught .then(); the S
    // namespace's own .then() is out of scope. S still participates as a step.)
    const pipeline = agent1
      .then(S.set({ topic: "x" }))
      .then(C.window(5))
      .then(A.publish("out.md", { fromKey: "draft" }))
      .then(agent2);

    expect(pipeline).toBeInstanceOf(Pipeline);
    const steps = (pipeline as unknown as { _lists: Map<string, unknown[]> })._lists.get(
      "sub_agents",
    )!;
    // Steps: [agent1, S.set, A.publish, agent2] — the C did NOT add a step.
    expect(steps.length).toBe(4);

    // The C bound to the last Agent present when it was applied (agent1, which
    // was the trailing Agent step before A.publish was appended).
    const writerStep = steps.find(
      (s) => s instanceof Agent && (s as Agent).name === "writer",
    ) as Agent;
    expect(writerStep).toBeDefined();
    expect(writerStep.inspect()["_context_spec"]).toBeInstanceOf(CTransform);

    // S and A are present as non-Agent steps (2 agents + 2 transforms).
    const agentSteps = steps.filter((s) => s instanceof Agent);
    expect(agentSteps).toHaveLength(2);

    // The whole thing still builds into a SequentialAgent with all 4 steps.
    const built = pipeline.build() as { _type: string; subAgents: unknown[] };
    expect(built._type).toBe("SequentialAgent");
    expect(built.subAgents.length).toBe(4);
  });

  it("C.then(agent) reverse-binds (chain may start with a C transform)", () => {
    const agent = new Agent("a", M).instruct("hi");
    const bound = C.window(5).then(agent) as Agent;
    expect(bound).toBeInstanceOf(Agent);
    expect(bound.inspect()["_context_spec"]).toBeInstanceOf(CTransform);
  });
});

describe("6. proceedIf()", () => {
  it("gate returns a skip marker when the predicate is falsy", () => {
    const agent = new Agent("a", M).proceedIf((s) => s.go === true);
    const before = callbacksOf(agent, "before_agent_callback");
    expect(before.length).toBeGreaterThan(0);

    const skip = before[0]({ state: { go: false } }) as { role?: string; parts?: unknown[] };
    expect(skip).toBeTruthy();
    expect(skip.role).toBe("model");
    expect(skip.parts).toEqual([]);

    // Truthy predicate → no skip (undefined).
    expect(before[0]({ state: { go: true } })).toBeUndefined();
  });

  it("PROPAGATES a thrown predicate error (does not swallow as skip)", () => {
    const agent = new Agent("a", M).proceedIf((s) => {
      // Simulate a typo'd key access that throws rather than returning falsy.
      if (!("present" in s)) throw new Error("boom: missing key");
      return true;
    });
    const before = callbacksOf(agent, "before_agent_callback");
    expect(() => before[0]({ state: {} })).toThrow(/boom: missing key/);
  });
});
