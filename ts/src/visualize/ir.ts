/**
 * Visualization IR.
 *
 * Renderers (mermaid, ascii, markdown, dot, …) operate on a single,
 * normalized tree of `VizNode` objects. The `normalize()` function turns
 * the tagged-config trees produced by every `.build()` into that shape.
 *
 * Every renderer is therefore independent of the source builder — the
 * same code visualizes a `Pipeline` build output, a hand-rolled config
 * literal, or a deserialized JSON dump from another process.
 */

/** A single node in the visualization tree. */
export interface VizNode {
  /** Discriminator. */
  kind:
    | "agent"
    | "sequence"
    | "parallel"
    | "loop"
    | "fallback"
    | "route"
    | "primitive"
    | "tool"
    | "unknown";
  /** Stable identifier (typically the builder `.name`). */
  name: string;
  /** Human-readable label shown in renderers. Defaults to `name`. */
  label: string;
  /** Original `_type` tag from the source object, when available. */
  source?: string;
  /** Free-form metadata renderers can surface (model, instruction, …). */
  meta: Record<string, unknown>;
  /** Composite children — pipeline steps, fan-out branches, loop body, etc. */
  children: VizNode[];
  /** Routing branches: each is a labelled edge to a child node. */
  branches?: { label: string; node: VizNode }[];
  /** Default branch on a Route. */
  defaultChild?: VizNode;
  /** Sub-agents that can receive transfer (LlmAgent.sub_agents). */
  transfers: VizNode[];
  /** Tool nodes attached directly to an agent. */
  tools: VizNode[];
  /** Number of guards (before+after model callbacks attached via `.guard()`). */
  guardCount: number;
}

/** Counter used to assign deterministic IDs when no `name` is present. */
class IdCounter {
  private n = 0;
  next(prefix: string): string {
    return `${prefix}_${this.n++}`;
  }
}

interface TaggedConfig {
  _type?: string;
  name?: string;
  description?: string;
  model?: string;
  instruction?: string | { render?: () => string };
  subAgents?: unknown[];
  sub_agents?: unknown[];
  children?: unknown[];
  branches?: { label?: string; predicate?: unknown; agent?: unknown }[];
  default?: unknown;
  tools?: unknown;
  before_model_callback?: unknown;
  after_model_callback?: unknown;
  maxIterations?: number;
  max_iterations?: number;
  _kind?: string;
  _agents?: unknown[];
  [key: string]: unknown;
}

const isObject = (v: unknown): v is Record<string, unknown> => typeof v === "object" && v !== null;

/** Make a shallow VizNode with all required arrays initialized. */
function blank(kind: VizNode["kind"], name: string, source?: string): VizNode {
  return {
    kind,
    name,
    label: name,
    source,
    meta: {},
    children: [],
    transfers: [],
    tools: [],
    guardCount: 0,
  };
}

/**
 * Normalize a tagged-config tree (or any builder build output) into the
 * visualization IR. Unknown shapes degrade to `kind: "unknown"` rather
 * than throwing.
 */
export function normalize(input: unknown): VizNode {
  return walk(input, new IdCounter());
}

function walk(input: unknown, ids: IdCounter): VizNode {
  if (!isObject(input)) {
    const node = blank("unknown", ids.next("value"));
    node.label = String(input);
    return node;
  }

  const cfg = input as TaggedConfig;
  const type = cfg._type;
  const name = typeof cfg.name === "string" && cfg.name ? cfg.name : ids.next("node");

  switch (type) {
    case "LlmAgent":
    case "BaseAgent": {
      const node = blank("agent", name, type);
      node.label = name;
      if (cfg.model) node.meta.model = cfg.model;
      if (cfg.description) node.meta.description = cfg.description;
      if (cfg.instruction) node.meta.instruction = renderInstruction(cfg.instruction);

      // sub_agents → transfer targets
      const subs = (cfg.sub_agents ?? cfg.subAgents ?? []) as unknown[];
      for (const s of subs) node.transfers.push(walk(s, ids));

      // tools → tool nodes
      for (const t of flattenTools(cfg.tools)) node.tools.push(toolNode(t, ids));

      node.guardCount = guardCount(cfg);
      return node;
    }

    case "SequentialAgent": {
      const node = blank("sequence", name, type);
      node.label = `${name} (sequence)`;
      const subs = (cfg.subAgents ?? cfg.sub_agents ?? []) as unknown[];
      for (const s of subs) node.children.push(walk(s, ids));
      return node;
    }

    case "ParallelAgent": {
      const node = blank("parallel", name, type);
      node.label = `${name} (parallel)`;
      const subs = (cfg.subAgents ?? cfg.sub_agents ?? []) as unknown[];
      for (const s of subs) node.children.push(walk(s, ids));
      return node;
    }

    case "LoopAgent": {
      const node = blank("loop", name, type);
      const max = cfg.maxIterations ?? cfg.max_iterations;
      node.label = max != null ? `${name} (loop ×${max})` : `${name} (loop)`;
      if (max != null) node.meta.maxIterations = max;
      const subs = (cfg.subAgents ?? cfg.sub_agents ?? []) as unknown[];
      for (const s of subs) node.children.push(walk(s, ids));
      return node;
    }

    case "Fallback": {
      const node = blank("fallback", name, type);
      node.label = `${name} (fallback)`;
      const children = (cfg.children ?? []) as unknown[];
      for (const c of children) node.children.push(walk(c, ids));
      return node;
    }

    case "Route": {
      const node = blank("route", name, type);
      const key = typeof cfg.key === "string" ? cfg.key : "?";
      node.label = `${name} (route on ${key})`;
      node.meta.key = key;
      node.branches = [];
      for (const b of cfg.branches ?? []) {
        const child = walk(b.agent, ids);
        node.branches.push({ label: b.label ?? "?", node: child });
      }
      if (cfg.default !== undefined && cfg.default !== null) {
        node.defaultChild = walk(cfg.default, ids);
      }
      return node;
    }

    case "Primitive": {
      const kind = typeof cfg._kind === "string" ? cfg._kind : "primitive";
      const node = blank("primitive", name, type);
      node.label = `${name} <${kind}>`;
      node.meta.kind = kind;
      const inner = (cfg._agents ?? []) as unknown[];
      for (const a of inner) node.children.push(walk(a, ids));
      return node;
    }

    default: {
      // Tools and unknown nodes — best-effort.
      if (typeof type === "string" && /Tool|Toolset$/.test(type)) {
        return toolNode(input, ids);
      }
      const node = blank("unknown", name, type);
      node.label = type ? `${name} <${type}>` : name;
      return node;
    }
  }
}

function renderInstruction(value: unknown): string {
  if (typeof value === "string") return value;
  if (isObject(value) && typeof (value as { render?: () => unknown }).render === "function") {
    try {
      const out = (value as { render: () => unknown }).render();
      if (typeof out === "string") return out;
    } catch {
      // fall through
    }
  }
  return "<callable instruction>";
}

function flattenTools(value: unknown): unknown[] {
  if (value == null) return [];
  if (Array.isArray(value)) return value.flatMap((v) => (Array.isArray(v) ? v : [v]));
  return [value];
}

function toolNode(value: unknown, ids: IdCounter): VizNode {
  if (!isObject(value)) {
    const n = blank("tool", ids.next("tool"));
    n.label = `tool: ${String(value)}`;
    return n;
  }
  const cfg = value as TaggedConfig;
  const type = cfg._type ?? "Tool";
  const name = typeof cfg.name === "string" && cfg.name ? cfg.name : ids.next("tool");
  const node = blank("tool", name, type);
  node.label = `${name} <${type}>`;
  return node;
}

function guardCount(cfg: TaggedConfig): number {
  let n = 0;
  if (cfg.before_model_callback != null) n += 1;
  if (cfg.after_model_callback != null) n += 1;
  return n;
}
