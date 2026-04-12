/**
 * 11 — Typed Output (.outputAs / Zod schema)
 *
 * Force the LLM to respond with structured output. Python uses
 * `agent @ PydanticModel`; TypeScript uses `.outputAs(zodSchema)`.
 *
 * The cookbook only asserts the schema is attached. Actual schema validation
 * happens at runtime when the agent runs against `@google/adk`.
 */
import assert from "node:assert/strict";
import { Agent } from "../../src/index.js";

// Plain TS interface — works as a documentation contract for human readers.
interface Classification {
  category: "billing" | "technical" | "general";
  confidence: number;
}

// Zod-shaped schema object. We don't import zod here to keep the cookbook
// dependency-free, but `.outputAs()` accepts any opaque schema descriptor.
const ClassificationSchema = {
  type: "object",
  properties: {
    category: { type: "string", enum: ["billing", "technical", "general"] },
    confidence: { type: "number" },
  },
  required: ["category", "confidence"],
} as const;

const agent = new Agent("classifier", "gemini-2.5-flash")
  .instruct("Classify the email.")
  .outputAs(ClassificationSchema)
  .build() as Record<string, unknown>;

assert.equal(agent._type, "LlmAgent");
// _output_schema is a private config key; the build path stores it on the
// builder for the @google/adk adapter to read at runtime.
const inspectable = new Agent("classifier", "gemini-2.5-flash")
  .instruct("Classify the email.")
  .outputAs(ClassificationSchema)
  .inspect();
assert.equal(inspectable._output_schema, ClassificationSchema);

// Documentation-only — TypeScript erases this at runtime.
const _docContract: Classification = { category: "billing", confidence: 0.92 };
void _docContract;

export { agent, ClassificationSchema };
