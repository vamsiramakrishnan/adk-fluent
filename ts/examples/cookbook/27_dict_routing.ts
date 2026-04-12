/**
 * 27 — Dict-style routing with `Route`
 *
 * Mirrors `python/examples/cookbook/18_dict_routing.py`.
 *
 * `Route` lets you express deterministic, state-key-based fan-out as a
 * lookup table. The routing decision is a pure function of state — no
 * LLM call, no token cost, completely reproducible.
 */
import assert from "node:assert/strict";
import { Agent, Route } from "../../src/index.js";

const vipDesk = new Agent("vip", "gemini-2.5-flash").instruct(
  "Greet a VIP customer with red-carpet service.",
);
const standardDesk = new Agent("standard", "gemini-2.5-flash").instruct(
  "Greet a standard customer politely.",
);
const freeDesk = new Agent("free", "gemini-2.5-flash").instruct(
  "Greet a free-tier customer briefly.",
);

const desk = new Route("tier")
  .eq("vip", vipDesk)
  .eq("standard", standardDesk)
  .otherwise(freeDesk);

const built = desk.build();

// The built shape is a tagged Route config — the visualization layer
// recognises it and the runtime walks the branches.
assert.equal(built._type, "Route");
assert.equal(built.key, "tier");
assert.equal(built.branches.length, 2);
assert.ok(built.default);

export { desk };
