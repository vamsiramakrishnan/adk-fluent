/**
 * 33 — Dispatch & Join: fire-and-continue background tasks
 *
 * Mirrors `python/examples/cookbook/59_dispatch_join.py`.
 *
 * Unlike FanOut (blocks until all complete) or race (first wins, others
 * cancelled), `dispatch()` launches an agent as a background task and
 * lets the pipeline continue immediately. `join()` is the barrier: wait
 * for all dispatched tasks to complete before continuing.
 */
import assert from "node:assert/strict";
import { Agent, Pipeline, dispatch, join } from "../../src/index.js";

const writer = new Agent("content_writer", "gemini-2.5-flash").instruct(
  "Write a blog post about the given topic.",
);
const emailSender = new Agent("email_sender", "gemini-2.5-flash").instruct(
  "Send email notification about the new content.",
);
const seoOptimizer = new Agent("seo_optimizer", "gemini-2.5-flash").instruct(
  "Optimize the content for search engines.",
);
const formatter = new Agent("formatter", "gemini-2.5-flash").instruct(
  "Format the content for the website.",
);
const publisher = new Agent("publisher", "gemini-2.5-flash").instruct(
  "Publish the formatted content.",
);

// Build the pipeline imperatively so we can intersperse primitives.
const pipeline = new Pipeline("publish_flow")
  .step(writer)
  .step(dispatch(emailSender, { name: "email" }))
  .step(dispatch(seoOptimizer, { name: "seo" }))
  .step(formatter)
  .step(join())
  .step(publisher)
  .build() as { _type: string; subAgents: Record<string, unknown>[] };

assert.equal(pipeline._type, "SequentialAgent");
assert.equal(pipeline.subAgents.length, 6);

// Each dispatch step is a Primitive tagged with kind="dispatch", and
// the join step is tagged with kind="join". The runtime walker reads
// these tags to dispatch on them.
const built = pipeline.subAgents.map((s) => s as Record<string, unknown>);
assert.equal(built[1]._type, "Primitive");
assert.equal(built[1]._kind, "dispatch");
assert.equal(built[2]._kind, "dispatch");
assert.equal(built[4]._kind, "join");

// onComplete callback is preserved for the runtime to invoke.
const seen: string[] = [];
const withCallback = dispatch(emailSender, {
  name: "email",
  onComplete: (result) => seen.push(String(result)),
});
const cbBuilt = withCallback.build() as Record<string, unknown>;
assert.equal(cbBuilt._kind, "dispatch");
assert.equal(typeof cbBuilt._on_complete, "function");

// join() with a name binds to a specific dispatched task.
const seoJoin = join("seo");
const joinBuilt = seoJoin.build() as Record<string, unknown>;
assert.equal(joinBuilt._kind, "join");
assert.equal(joinBuilt.name, "seo");

export { pipeline };
