/**
 * builder-serialization — dict / YAML / native (de)serialization for builders.
 *
 * The TypeScript counterpart of Python's `_base_serialization.py`. Factored out
 * of `builder-base.ts` so the builder class stays focused on the fluent
 * surface. These are free functions operating on a builder's internal state via
 * a narrow {@link BuilderState} view (the maps are `protected` on the class, so
 * the cast is the single, documented boundary).
 *
 * `builder-base.ts` imports these and exposes them as thin `toDict` / `fromDict`
 * / `toYaml` / `fromYaml` / `fromNative` methods, so the public API is
 * unchanged. The `BuilderBase` value import forms a cycle with `builder-base`,
 * but every reference is inside a function body (call-time), so ESM live
 * bindings resolve it safely — nothing here runs at module-evaluation time.
 */

import {
  detectNativeKind,
  getWorkflow,
  moduleRequire,
  resolveBuilderClass,
} from "./builder-internals.js";
import { BuilderBase } from "./builder-base.js";

/** Internal view of a builder's protected state maps. */
interface BuilderState {
  _config: Map<string, unknown>;
  _callbacks: Map<string, unknown[]>;
  _lists: Map<string, unknown[]>;
}

/** Narrow a builder to its internal state maps (the one documented boundary). */
function state(b: BuilderBase): BuilderState {
  return b as unknown as BuilderState;
}

/**
 * Serialize a single value for dict/yaml output. Nested builders recurse via
 * {@link toDict}; callables collapse to their name string (NOT round-trippable).
 * Mirrors Python `_serialize_value`.
 */
export function serializeValue(v: unknown): unknown {
  if (v instanceof BuilderBase) return v.toDict();
  if (Array.isArray(v)) return v.map((x) => serializeValue(x));
  if (typeof v === "function") {
    return (v as { name?: string }).name || "<fn>";
  }
  if (v && typeof v === "object") {
    // Only plain objects round-trip cleanly; tag exotic class instances.
    const proto = Object.getPrototypeOf(v);
    if (proto === Object.prototype || proto === null) {
      const out: Record<string, unknown> = {};
      for (const [k, val] of Object.entries(v as Record<string, unknown>)) {
        out[k] = serializeValue(val);
      }
      return out;
    }
    const name = (v as { name?: string }).name;
    return name ? `<obj:${name}>` : String(v);
  }
  return v;
}

/**
 * Deserialization dual of {@link serializeValue}. Reconstructs nested
 * builder-dicts (`{ _type: ... }`) into builders, recursing through
 * arrays/objects. Scalars and callable-name strings pass through unchanged
 * (callables are NOT restored). Mirrors Python `_revive_value`.
 */
export function reviveValue(v: unknown): unknown {
  if (v && typeof v === "object" && !Array.isArray(v) && "_type" in (v as object)) {
    return fromDict(v as Record<string, unknown>);
  }
  if (Array.isArray(v)) return v.map((x) => reviveValue(x));
  if (v && typeof v === "object") {
    const proto = Object.getPrototypeOf(v);
    if (proto === Object.prototype || proto === null) {
      const out: Record<string, unknown> = {};
      for (const [k, val] of Object.entries(v as Record<string, unknown>)) {
        out[k] = reviveValue(val);
      }
      return out;
    }
  }
  return v;
}

/**
 * Serialize builder state to a plain dict: `{ _type, config, callbacks, lists }`.
 * A structural snapshot — config scalars and nested builder topology round-trip
 * via {@link fromDict}, but callables are stored as name-only strings and are
 * NOT restored. Mirrors Python `_base.py::to_dict`.
 */
export function toDict(self: BuilderBase): Record<string, unknown> {
  const s = state(self);
  const config: Record<string, unknown> = {};
  for (const [k, v] of s._config) {
    if (k.startsWith("_")) continue;
    config[k] = serializeValue(v);
  }
  const callbacks: Record<string, string[]> = {};
  for (const [field, fns] of s._callbacks) {
    if (field.startsWith("_") || fns.length === 0) continue;
    callbacks[field] = fns.map((fn) => String(serializeValue(fn)));
  }
  const lists: Record<string, unknown[]> = {};
  for (const [field, items] of s._lists) {
    if (field.startsWith("_") || items.length === 0) continue;
    lists[field] = items.map((item) => serializeValue(item));
  }
  return {
    _type: self.constructor.name,
    config,
    callbacks,
    lists,
  };
}

/**
 * Reconstruct a builder from a {@link toDict} payload. Structural round-trip:
 * restores builder *type*, config scalars, and nested builder topology
 * (recursively). Callables are NOT restored. Mirrors Python `_base.py::from_dict`.
 */
export function fromDict(data: Record<string, unknown>): BuilderBase {
  const typeName = (data._type as string) ?? "Agent";
  const builderCls = resolveBuilderClass(typeName);
  const config = { ...((data.config as Record<string, unknown>) ?? {}) };
  const name = (config.name as string) ?? "";
  const obj = new builderCls(name);
  const s = state(obj);
  for (const [key, value] of Object.entries(config)) {
    if (key === "name") continue;
    s._config.set(key, reviveValue(value));
  }
  const lists = (data.lists as Record<string, unknown[]>) ?? {};
  for (const [field, items] of Object.entries(lists)) {
    for (const item of items) {
      if (item && typeof item === "object" && "_type" in (item as object)) {
        const bucket = (s._lists.get(field) ?? []) as unknown[];
        bucket.push(fromDict(item as Record<string, unknown>));
        s._lists.set(field, bucket);
      }
    }
  }
  return obj;
}

/**
 * Serialize builder state to a YAML string. Requires the optional `yaml`
 * package; throws a clear Error if it is not installed. Shares the
 * structural-snapshot limitations of {@link toDict}.
 */
export function toYaml(self: BuilderBase): string {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  let yaml: any;
  try {
    yaml = moduleRequire("yaml");
  } catch {
    throw new Error(
      "toYaml() requires the optional 'yaml' package. Install it with: npm install yaml",
    );
  }
  return yaml.stringify(toDict(self));
}

/**
 * Reconstruct a builder from YAML produced by {@link toYaml}. `source` may be a
 * YAML string or a path to a `.yaml` / `.yml` file. Requires the optional
 * `yaml` package. Shares {@link fromDict}'s structural round-trip semantics.
 * Mirrors Python `_base.py::from_yaml`.
 */
export function fromYaml(source: string): BuilderBase {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  let yaml: any;
  try {
    yaml = moduleRequire("yaml");
  } catch {
    throw new Error(
      "fromYaml() requires the optional 'yaml' package. Install it with: npm install yaml",
    );
  }
  let text = source;
  if (!source.includes("\n") && /\.(ya?ml)$/.test(source)) {
    try {
      const fs = moduleRequire("fs");
      if (fs.existsSync(source)) {
        text = fs.readFileSync(source, "utf8");
      }
    } catch {
      /* treat source as inline YAML */
    }
  }
  const data = yaml.parse(text) as Record<string, unknown>;
  return fromDict(data);
}

/**
 * Adopt a native ADK agent object as a fluent builder — the inverse of
 * `build()`. Recovers name / model / instruction / description / tools and
 * sub-agent topology (recursively) for the four core agent types. Accepts both
 * real `@google/adk` objects and the tagged dicts produced by `.build()`.
 * Throws a clear Error for unsupported native types. Mirrors Python
 * `_base.py::from_native`.
 */
export function fromNative(native: unknown): BuilderBase {
  if (native == null || typeof native !== "object") {
    throw new Error(`fromNative: expected a native ADK agent object, got ${typeof native}.`);
  }
  const n = native as Record<string, unknown>;
  const kind = detectNativeKind(native);
  const name = (n.name as string) ?? "";

  const carryDescription = (b: BuilderBase): void => {
    const desc = n.description;
    if (desc) state(b)._config.set("description", desc);
  };
  const subAgentsOf = (): unknown[] =>
    (n.subAgents as unknown[]) ?? (n.sub_agents as unknown[]) ?? [];

  if (kind === "SequentialAgent" || kind === "ParallelAgent" || kind === "LoopAgent") {
    const children = subAgentsOf().map((c) => fromNative(c));
    let builder: BuilderBase;
    if (kind === "SequentialAgent") {
      builder = new (getWorkflow("Pipeline"))(name);
    } else if (kind === "ParallelAgent") {
      builder = new (getWorkflow("FanOut"))(name);
    } else {
      builder = new (getWorkflow("Loop"))(name);
      const maxIter = (n.maxIterations as number) ?? (n.max_iterations as number);
      if (maxIter) state(builder)._config.set("max_iterations", maxIter);
    }
    state(builder)._lists.set("sub_agents", children);
    carryDescription(builder);
    return builder;
  }

  if (kind === "LlmAgent") {
    const model = n.model;
    const modelStr =
      typeof model === "string"
        ? model
        : ((model as { model?: string } | null)?.model ?? undefined);
    const AgentCtor = resolveBuilderClass("Agent");
    const builder = new AgentCtor(name);
    const s = state(builder);
    if (modelStr) s._config.set("model", modelStr);
    const instr = n.instruction;
    if (instr) s._config.set("instruction", instr);
    carryDescription(builder);
    const tools = (n.tools as unknown[]) ?? [];
    if (tools.length > 0) s._lists.set("tools", [...tools]);
    const subs = subAgentsOf();
    if (subs.length > 0) {
      s._lists.set(
        "sub_agents",
        subs.map((sub) => fromNative(sub)),
      );
    }
    return builder;
  }

  throw new Error(
    `fromNative: unsupported native agent type. ` +
      `Supported: LlmAgent, SequentialAgent, ParallelAgent, LoopAgent.`,
  );
}
