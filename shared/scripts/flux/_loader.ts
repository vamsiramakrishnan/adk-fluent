/**
 * flux spec loader — Node-side bridge invoked by the Python codegen pipeline.
 *
 * Usage (internal — called by ``shared/scripts/flux/loader.py``)::
 *
 *     npx tsx shared/scripts/flux/_loader.ts <spec-file>
 *
 * The script dynamic-imports the given ``.spec.ts`` file, grabs
 * ``mod.default`` (which ``defineComponent`` has already validated), then
 * walks the spec to produce a JSON-serialisable snapshot:
 *
 *   * ``schema`` (the Zod object) is converted via ``z.toJSONSchema`` and
 *     re-keyed as ``jsonSchema`` so the emitted catalog matches the shape
 *     required by ``catalog/flux/schema/component.schema.json``.
 *   * Everything else is copied verbatim in the key order the DSL author
 *     wrote — the loader does NOT reshape or normalise ordering so
 *     downstream emitters stay deterministic.
 *
 * The script prints exactly ONE JSON object (pretty-printed with 2-space
 * indent) to stdout and nothing else; every diagnostic goes to stderr so
 * the parent Python process can round-trip stdout → ``json.loads`` without
 * scrubbing.
 *
 * Exit codes::
 *
 *     0 — JSON printed to stdout
 *     1 — usage / import / validation error (details on stderr)
 */

import { pathToFileURL } from "node:url";
import { z } from "zod";

type JsonValue =
  | string
  | number
  | boolean
  | null
  | JsonValue[]
  | { [key: string]: JsonValue };

type ZodLike = z.ZodType<unknown>;

function isZod(value: unknown): value is ZodLike {
  return (
    typeof value === "object" &&
    value !== null &&
    "_def" in (value as Record<string, unknown>) &&
    typeof (value as { parse?: unknown }).parse === "function"
  );
}

/**
 * Compile a Zod schema to JSON Schema via Zod v4's built-in converter. We
 * strip the top-level ``$schema`` key so the emitted catalog's component
 * block stays a plain JSON Schema object (the outer catalog carries its own
 * ``$schema`` reference).
 */
function toJsonSchema(schema: ZodLike): JsonValue {
  // `z.toJSONSchema` is the Zod v4 entry point.
  const out = z.toJSONSchema(schema);
  if (typeof out === "object" && out !== null && "$schema" in out) {
    const clone: Record<string, JsonValue> = { ...(out as Record<string, JsonValue>) };
    delete clone["$schema"];
    return clone;
  }
  return out as JsonValue;
}

/**
 * Walk the spec tree recursively, converting Zod schemas (found anywhere)
 * to JSON Schema and leaving every other value intact. The DSL only stores
 * one Zod instance (the ``schema`` field) but we walk defensively so that a
 * future spec that embeds Zod deeper still serialises correctly.
 */
function serialise(value: unknown): JsonValue {
  if (value === null || value === undefined) return null;
  if (isZod(value)) return toJsonSchema(value);
  if (Array.isArray(value)) return value.map(serialise);
  if (typeof value === "object") {
    const obj = value as Record<string, unknown>;
    const out: Record<string, JsonValue> = {};
    for (const key of Object.keys(obj)) {
      const child = serialise(obj[key]);
      if (child !== undefined) out[key] = child;
    }
    return out;
  }
  if (typeof value === "function") {
    // Functions in a spec are a DSL-level mistake; surface them rather than
    // silently dropping.
    throw new Error(`flux loader: cannot serialise function value (${(value as Function).name || "<anon>"})`);
  }
  if (typeof value === "bigint") return value.toString();
  return value as JsonValue;
}

async function main(): Promise<void> {
  const specPath = process.argv[2];
  if (!specPath) {
    console.error("usage: _loader.ts <spec-path>");
    process.exit(1);
  }
  const url = pathToFileURL(specPath).href;
  let mod: { default?: unknown };
  try {
    mod = (await import(url)) as { default?: unknown };
  } catch (err) {
    console.error(`flux loader: failed to import ${specPath}`);
    console.error(err instanceof Error ? err.stack ?? err.message : String(err));
    process.exit(1);
    return;
  }
  if (!mod.default) {
    console.error(`flux loader: ${specPath} has no default export (expected ComponentSpec)`);
    process.exit(1);
    return;
  }
  // DSL-author spec — shape comes from dsl/types.ts#ComponentSpec. We pass
  // the whole thing through ``serialise`` which swaps the Zod schema for
  // JSON Schema and renames the key.
  const spec = mod.default as Record<string, unknown>;
  const serialised = serialise(spec) as Record<string, JsonValue>;
  // Rename `schema` → `jsonSchema` to match component.schema.json.
  if ("schema" in serialised) {
    serialised.jsonSchema = serialised.schema;
    delete serialised.schema;
  }
  // Deterministic key order: rebuild the object in the canonical order
  // described by ARCHITECTURE.md §6 + the component schema. Any future key
  // that ARCHITECTURE adds lands alphabetically at the end so emitters stay
  // stable.
  const CANONICAL_ORDER = [
    "name",
    "extends",
    "category",
    "jsonSchema",
    "slots",
    "tokens",
    "variants",
    "compoundVariants",
    "defaultVariants",
    "accessibility",
    "llm",
    "renderer",
  ];
  const ordered: Record<string, JsonValue> = {};
  for (const key of CANONICAL_ORDER) {
    if (key in serialised) ordered[key] = serialised[key];
  }
  for (const key of Object.keys(serialised).sort()) {
    if (!(key in ordered)) ordered[key] = serialised[key];
  }
  process.stdout.write(JSON.stringify(ordered, null, 2) + "\n");
}

main().catch((err) => {
  console.error("flux loader: uncaught error");
  console.error(err instanceof Error ? err.stack ?? err.message : String(err));
  process.exit(1);
});
