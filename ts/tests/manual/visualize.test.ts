/**
 * Tests for the visualization layer.
 *
 * Asserts that:
 * - normalize() turns tagged-config trees into the expected VizNode shape
 * - the ascii / mermaid / markdown / json renderers all produce non-empty
 *   output for every node kind we ship (agent, sequence, parallel, loop,
 *   fallback, route, primitive)
 * - BuilderBase.visualize() round-trips through .build() correctly
 */
import { describe, expect, it } from "vitest";
import { Agent } from "../../src/builders/agent.js";
import { FanOut, Loop, Pipeline, Fallback } from "../../src/builders/workflow.js";
import { Route } from "../../src/routing/index.js";
import { tap } from "../../src/primitives/index.js";
import {
  normalize,
  renderAscii,
  renderMarkdown,
  renderMermaid,
  visualize,
  type VizNode,
} from "../../src/visualize/index.js";

function buildSamplePipeline(): unknown {
  const writer = new Agent("writer", "gemini-2.5-flash")
    .instruct("Draft the report.")
    .writes("draft");
  const critic = new Agent("critic", "gemini-2.5-flash")
    .instruct("Review the {draft}.")
    .writes("feedback");

  const fanout = new FanOut("research")
    .branch(new Agent("web", "gemini-2.5-flash").instruct("Search web."))
    .branch(new Agent("papers", "gemini-2.5-flash").instruct("Search papers."));

  const loop = new Loop("refine").step(writer).step(critic).maxIterations(3);

  return new Pipeline("flow").step(fanout).step(loop).build();
}

describe("normalize()", () => {
  it("normalizes a Pipeline + FanOut + Loop tree", () => {
    const node = normalize(buildSamplePipeline());
    expect(node.kind).toBe("sequence");
    expect(node.name).toBe("flow");
    expect(node.children).toHaveLength(2);
    expect(node.children[0].kind).toBe("parallel");
    expect(node.children[0].children).toHaveLength(2);
    expect(node.children[1].kind).toBe("loop");
    expect(node.children[1].meta.maxIterations).toBe(3);
    expect(node.children[1].children).toHaveLength(2);
    expect(node.children[1].children[0].kind).toBe("agent");
    expect(node.children[1].children[0].meta.model).toBe("gemini-2.5-flash");
    expect(node.children[1].children[0].meta.instruction).toBe("Draft the report.");
  });

  it("normalizes a Route", () => {
    const vip = new Agent("vip", "gemini-2.5-pro").instruct("White-glove.");
    const std = new Agent("std", "gemini-2.5-flash").instruct("Standard.");
    const config = new Route("tier").eq("VIP", vip).otherwise(std).build();

    const node = normalize(config);
    expect(node.kind).toBe("route");
    expect(node.meta.key).toBe("tier");
    expect(node.branches).toHaveLength(1);
    expect(node.branches?.[0].label).toBe("eq:VIP");
    expect(node.branches?.[0].node.name).toBe("vip");
    expect(node.defaultChild?.name).toBe("std");
  });

  it("normalizes a Fallback chain", () => {
    const a = new Agent("fast", "gemini-2.5-flash").instruct("Fast path.");
    const b = new Agent("slow", "gemini-2.5-pro").instruct("Slow path.");
    const config = new Fallback("resilient").attempt(a).attempt(b).build();
    const node = normalize(config);
    expect(node.kind).toBe("fallback");
    expect(node.children).toHaveLength(2);
    expect(node.children[0].name).toBe("fast");
  });

  it("normalizes a primitive (tap)", () => {
    const config = tap(() => {}).build();
    const node = normalize(config);
    expect(node.kind).toBe("primitive");
    expect(node.meta.kind).toBe("tap");
  });

  it("flags guards on agents", () => {
    const config = new Agent("guarded", "gemini-2.5-flash")
      .instruct("Hello.")
      .guard(() => undefined)
      .build() as Record<string, unknown>;
    const node = normalize(config);
    expect(node.guardCount).toBe(2);
  });

  it("degrades gracefully on unknown shapes", () => {
    const node = normalize({ _type: "Mystery", name: "x" });
    expect(node.kind).toBe("unknown");
    expect(node.source).toBe("Mystery");
  });
});

describe("renderAscii()", () => {
  it("produces a tree with box-drawing characters", () => {
    const node = normalize(buildSamplePipeline());
    const out = renderAscii(node);
    expect(out).toContain("flow");
    expect(out).toContain("[seq]");
    expect(out).toContain("[par]");
    expect(out).toContain("[loop]");
    expect(out).toContain("├──");
    expect(out).toContain("└──");
  });

  it("includes meta lines when showMeta is true", () => {
    const node = normalize(buildSamplePipeline());
    const out = renderAscii(node, { showMeta: true });
    expect(out).toContain("model: gemini-2.5-flash");
    expect(out).toContain("max: 3");
  });

  it("omits meta when showMeta is false", () => {
    const node = normalize(buildSamplePipeline());
    const out = renderAscii(node, { showMeta: false });
    expect(out).not.toContain("model:");
  });
});

describe("renderMermaid()", () => {
  it("produces a flowchart with TD direction", () => {
    const node = normalize(buildSamplePipeline());
    const out = renderMermaid(node);
    expect(out.startsWith("flowchart TD")).toBe(true);
    expect(out).toContain("flow");
    expect(out).toContain("research");
    expect(out).toContain("-->");
  });

  it("renders route branches with labelled edges", () => {
    const vip = new Agent("vip", "gemini-2.5-pro").instruct("VIP.");
    const std = new Agent("std", "gemini-2.5-flash").instruct("Standard.");
    const config = new Route("tier").eq("VIP", vip).otherwise(std).build();
    const out = renderMermaid(normalize(config));
    expect(out).toContain('-- "eq:VIP" -->');
    expect(out).toContain('-- "(default)" -->');
  });

  it("supports fenced output", () => {
    const node: VizNode = normalize(buildSamplePipeline());
    const out = renderMermaid(node, { fenced: true });
    expect(out.startsWith("```mermaid")).toBe(true);
    expect(out.endsWith("```")).toBe(true);
  });
});

describe("renderMarkdown()", () => {
  it("emits headings and a fact table", () => {
    const node = normalize(buildSamplePipeline());
    const out = renderMarkdown(node);
    expect(out).toContain("## flow");
    expect(out).toContain("| field | value |");
    expect(out).toContain("```mermaid");
  });
});

describe("visualize()", () => {
  it("dispatches on format", () => {
    const config = buildSamplePipeline();
    expect(visualize(config, { format: "ascii" })).toContain("[seq]");
    expect(visualize(config, { format: "mermaid" })).toContain("flowchart TD");
    expect(visualize(config, { format: "markdown" })).toContain("```mermaid");
    const json = visualize(config, { format: "json" });
    expect(JSON.parse(json).kind).toBe("sequence");
  });
});

describe("BuilderBase.visualize()", () => {
  it("is callable directly on a builder", () => {
    const pipeline = new Pipeline("demo")
      .step(new Agent("a", "gemini-2.5-flash").instruct("First."))
      .step(new Agent("b", "gemini-2.5-flash").instruct("Second."));
    const out = pipeline.visualize();
    expect(out).toContain("demo");
    expect(out).toContain("[seq]");
  });

  it("forwards format options", () => {
    const agent = new Agent("solo", "gemini-2.5-flash").instruct("Hi.");
    expect(agent.visualize({ format: "mermaid" })).toContain("flowchart TD");
  });
});
