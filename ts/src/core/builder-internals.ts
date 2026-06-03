/**
 * builder-internals — registry + runtime plumbing for {@link BuilderBase}.
 *
 * Factored out of `builder-base.ts` to keep the builder class focused on the
 * fluent surface. Holds three concerns that are pure free-function plumbing:
 *
 * - the workflow / builder-class registries (populated at module load to
 *   sidestep circular ESM imports), and their resolvers;
 * - native ADK agent classification (`detectNativeKind`) used by `fromNative`;
 * - lazy loaders for optional deps (`@google/adk` type guards, and a CJS-style
 *   `require` for `yaml`/`fs`).
 *
 * Only a *type* reference to `BuilderBase` is needed here, so the import is
 * `import type` — there is no runtime cycle back into `builder-base.ts`.
 */

import { createRequire } from "module";
import type { BuilderBase } from "./builder-base.js";

/**
 * A CJS-style `require` usable from ESM. Used to lazily load optional
 * dependencies (`yaml`, `fs`) and `@google/adk` type guards without forcing
 * them into the static import graph.
 */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export const moduleRequire: (id: string) => any = createRequire(import.meta.url);

// ------------------------------------------------------------------
// Workflow registry — populated by workflow.ts at module load to avoid
// circular ESM imports between builder-base.ts and workflow.ts.
// ------------------------------------------------------------------

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const _workflowRegistry: Record<string, any> = {};

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function registerWorkflow(name: string, ctor: any): void {
  _workflowRegistry[name] = ctor;
}

export function getWorkflow(name: string): {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  new (...args: any[]): BuilderBase;
} {
  const ctor = _workflowRegistry[name];
  if (!ctor) {
    throw new Error(
      `Workflow class "${name}" not registered. Make sure builders/workflow.js is imported.`,
    );
  }
  return ctor;
}

// ------------------------------------------------------------------
// Builder-class registry for fromDict / fromNative reconstruction.
// Populated lazily so non-workflow builders (Agent, BaseAgent) can be
// resolved without a static import cycle.
// ------------------------------------------------------------------

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const _builderClassRegistry: Record<string, new (...args: any[]) => BuilderBase> = {};

/** Register a builder class for serialization round-trips. */
export function registerBuilderClass(
  name: string,
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  ctor: new (...args: any[]) => BuilderBase,
): void {
  _builderClassRegistry[name] = ctor;
}

/**
 * Resolve a serialized `_type` name back to its builder class. Workflow
 * classes come from the workflow registry; Agent / BaseAgent come from the
 * builder-class registry. Mirrors Python `_resolve_builder_class`.
 */
export function resolveBuilderClass(typeName: string): {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  new (...args: any[]): BuilderBase;
} {
  if (typeName in _workflowRegistry) return _workflowRegistry[typeName];
  if (typeName in _builderClassRegistry) return _builderClassRegistry[typeName];
  throw new Error(
    `fromDict/fromNative: unknown builder type "${typeName}". ` +
      `Known: ${[...Object.keys(_workflowRegistry), ...Object.keys(_builderClassRegistry)].sort().join(", ")}. ` +
      `Ensure builders/agent.js and builders/workflow.js are imported.`,
  );
}

// ------------------------------------------------------------------
// Native ADK agent classification (used by fromNative)
// ------------------------------------------------------------------

/** Lazily load @google/adk for its type guards. Returns null if unavailable. */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
let _adkCache: any = undefined;
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function loadAdk(): any {
  if (_adkCache !== undefined) return _adkCache;
  try {
    _adkCache = moduleRequire("@google/adk");
  } catch {
    _adkCache = null;
  }
  return _adkCache;
}

/**
 * Classify a native ADK agent object into one of the four core kinds.
 *
 * Handles (a) the tagged dicts produced by this package's `.build()`
 * (which carry a `_type` field) and (b) real `@google/adk` objects
 * (whose `constructor.name` is minified, so we use the `is*Agent` type
 * guards plus structural duck-typing). Returns `null` when unrecognized.
 */
export function detectNativeKind(
  native: unknown,
): "LlmAgent" | "SequentialAgent" | "ParallelAgent" | "LoopAgent" | null {
  if (native == null || typeof native !== "object") return null;
  const n = native as Record<string, unknown>;

  // (a) Tagged build-dict from this package.
  const tagged = n._type;
  if (
    tagged === "LlmAgent" ||
    tagged === "SequentialAgent" ||
    tagged === "ParallelAgent" ||
    tagged === "LoopAgent"
  ) {
    return tagged;
  }

  // (b) Real @google/adk object — use the package's type guards if present.
  try {
    const adk = loadAdk();
    if (adk) {
      if (typeof adk.isLoopAgent === "function" && adk.isLoopAgent(native)) return "LoopAgent";
      if (typeof adk.isSequentialAgent === "function" && adk.isSequentialAgent(native))
        return "SequentialAgent";
      if (typeof adk.isParallelAgent === "function" && adk.isParallelAgent(native))
        return "ParallelAgent";
      if (typeof adk.isLlmAgent === "function" && adk.isLlmAgent(native)) return "LlmAgent";
    }
  } catch {
    /* fall through to structural detection */
  }

  // (c) Structural fallback: a constructor name match or instruction presence.
  const ctorName = (native.constructor && native.constructor.name) || "";
  if (
    ctorName === "LlmAgent" ||
    ctorName === "SequentialAgent" ||
    ctorName === "ParallelAgent" ||
    ctorName === "LoopAgent"
  ) {
    return ctorName as "LlmAgent" | "SequentialAgent" | "ParallelAgent" | "LoopAgent";
  }
  if ("maxIterations" in n || "max_iterations" in n) return "LoopAgent";
  if ("instruction" in n || "model" in n) return "LlmAgent";
  if ("subAgents" in n || "sub_agents" in n) return "SequentialAgent";
  return null;
}
