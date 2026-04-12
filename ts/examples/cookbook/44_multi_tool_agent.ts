/**
 * 44 — Multi-tool task agent
 *
 * Mirrors `python/examples/cookbook/58_multi_tool_agent.py`.
 *
 * A versatile task agent with multiple function tools, an output guard,
 * and a verifier downstream that reads the task result via context
 * injection.
 */
import assert from "node:assert/strict";
import { Agent, Pipeline, T, G, C } from "../../src/index.js";

const MODEL = "gemini-2.5-flash";

// Plain function tools — `T.fn()` wraps them as FunctionTools.
function searchWeb(args: { query: string }): unknown {
  return { results: [`hit for ${args.query}`] };
}
function calculate(args: { expression: string }): unknown {
  // Real implementation would parse-and-evaluate; we keep it inert.
  return { value: args.expression };
}
function readFile(args: { path: string }): unknown {
  return { contents: `<<contents of ${args.path}>>` };
}

// Compose three tools into a single TComposite.
const taskTools = T.fn(searchWeb as never, { description: "Search the web for a query" })
  .pipe(T.fn(calculate as never, { description: "Evaluate an arithmetic expression" }))
  .pipe(T.fn(readFile as never, { description: "Read a file from storage" }));

assert.equal(taskTools.items.length, 3);

// Build the task agent: tools + length guard + output key.
const taskAgent = new Agent("task_agent", MODEL)
  .instruct(
    "You are a versatile task agent. Use the available tools to complete " +
      "the user's request and report the result clearly.",
  )
  .tools(taskTools)
  .guard(G.length({ max: 4000 }))
  .writes("task_result");

const builtTask = taskAgent.build() as Record<string, unknown> & { tools: unknown[] };
assert.equal(builtTask._type, "LlmAgent");
assert.ok(Array.isArray(builtTask.tools) && builtTask.tools.length > 0);
assert.equal(builtTask.output_key, "task_result");

// A verifier reads the task result via injected state context.
const verifier = new Agent("verifier", MODEL)
  .instruct("Verify the task result for correctness and surface any concerns.")
  .context(C.none().add(C.fromState("task_result")));

const pipeline = new Pipeline("multi_tool_flow").step(taskAgent).step(verifier).build() as {
  _type: string;
  subAgents: Record<string, unknown>[];
};

assert.equal(pipeline._type, "SequentialAgent");
assert.equal(pipeline.subAgents.length, 2);
assert.equal((pipeline.subAgents[0] as { name: string }).name, "task_agent");
assert.equal((pipeline.subAgents[1] as { name: string }).name, "verifier");

export { pipeline };
