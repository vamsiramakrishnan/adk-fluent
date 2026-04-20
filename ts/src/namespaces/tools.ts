/**
 * T — Tool composition namespace.
 *
 * Factory methods returning composable tool collections.
 * Compose with .pipe() to combine tool sets.
 *
 * Usage:
 *   agent.tools(T.fn(search).pipe(T.fn(email)))
 *   agent.tools(T.googleSearch().pipe(T.fn(calculator)))
 */

import { existsSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

import type { ToolFn } from "../core/types.js";
import type { BuilderBase } from "../core/builder-base.js";
import { A2UIError, A2UINotInstalled } from "../_exceptions.js";
import { KNOWN_CATALOGS, type CatalogName } from "./ui.js";

/** Descriptor for a single tool in the composite. */
export interface ToolSpec {
  type: string;
  [key: string]: unknown;
}

/** A composable tool collection. */
export class TComposite {
  constructor(public readonly items: ToolSpec[]) {}

  /** Chain: combine with another tool collection. */
  pipe(other: TComposite): TComposite {
    return new TComposite([...this.items, ...other.items]);
  }

  /** Convert to a flat tool array for passing to builder. */
  toArray(): ToolSpec[] {
    return [...this.items];
  }

  /**
   * Attach this tool collection to a builder. Mirrors Python's
   * ``T.fn(a) | T.fn(b) >> Agent(...)``. Returns the builder with
   * this composite set as the agent's tools.
   */
  attachTo<B extends BuilderBase>(builder: B): B {
    const setter = (builder as unknown as { tools: (v: unknown) => B }).tools;
    if (typeof setter !== "function") {
      throw new TypeError(
        `TComposite.attachTo: builder has no .tools() method (builder is ${builder.constructor.name})`,
      );
    }
    return setter.call(builder, this);
  }
}

/**
 * T namespace — tool composition factories.
 *
 * All 16 methods from the Python T namespace.
 */
export class T {
  // ------------------------------------------------------------------
  // Core tool types
  // ------------------------------------------------------------------

  /** Wrap a callable as a FunctionTool. Optionally require confirmation. */
  static fn(
    callable: ToolFn,
    opts?: { name?: string; description?: string; confirm?: boolean },
  ): TComposite {
    return new TComposite([
      {
        type: "function",
        fn: callable,
        name: opts?.name,
        description: opts?.description,
        confirm: opts?.confirm ?? false,
      },
    ]);
  }

  /** Wrap an agent/builder as an AgentTool. */
  static agent(agent: unknown, opts?: { name?: string; description?: string }): TComposite {
    return new TComposite([{ type: "agent_tool", agent, ...opts }]);
  }

  /** Wrap an ADK toolset (MCP, OpenAPI, etc.). */
  static toolset(ts: unknown): TComposite {
    return new TComposite([{ type: "toolset", toolset: ts }]);
  }

  // ------------------------------------------------------------------
  // Built-in tools
  // ------------------------------------------------------------------

  /** Google Search built-in tool. */
  static googleSearch(): TComposite {
    return new TComposite([{ type: "google_search" }]);
  }

  // ------------------------------------------------------------------
  // Dynamic tool loading
  // ------------------------------------------------------------------

  /** BM25-indexed dynamic tool loading from a registry. */
  static search(
    registry: unknown,
    opts?: { alwaysLoaded?: string[]; maxTools?: number },
  ): TComposite {
    return new TComposite([
      {
        type: "search",
        registry,
        alwaysLoaded: opts?.alwaysLoaded,
        maxTools: opts?.maxTools ?? 20,
      },
    ]);
  }

  /** Attach a ToolSchema for contract checking. */
  static schema(schemaCls: unknown): TComposite {
    return new TComposite([{ type: "schema", schema: schemaCls }]);
  }

  // ------------------------------------------------------------------
  // Protocol tools
  // ------------------------------------------------------------------

  /** MCP toolset factory. */
  static mcp(
    urlOrParams: string | Record<string, unknown>,
    opts?: { toolFilter?: string[]; prefix?: string },
  ): TComposite {
    return new TComposite([
      {
        type: "mcp",
        params: typeof urlOrParams === "string" ? { url: urlOrParams } : urlOrParams,
        toolFilter: opts?.toolFilter,
        prefix: opts?.prefix,
      },
    ]);
  }

  /** OpenAPI spec tool. */
  static openapi(
    spec: string | Record<string, unknown>,
    opts?: { toolFilter?: string[]; auth?: Record<string, unknown> },
  ): TComposite {
    return new TComposite([
      {
        type: "openapi",
        spec,
        toolFilter: opts?.toolFilter,
        auth: opts?.auth,
      },
    ]);
  }

  /** Wrap remote A2A agent as AgentTool. */
  static a2a(
    agentCardUrl: string,
    opts?: { name?: string; description?: string; timeout?: number },
  ): TComposite {
    return new TComposite([
      {
        type: "a2a",
        agentCardUrl,
        name: opts?.name,
        description: opts?.description,
        timeout: opts?.timeout ?? 600,
      },
    ]);
  }

  /**
   * A2UI toolset — exposes UI generation/binding tools to the LLM.
   *
   * Catalog dispatch:
   * - **basic** (default): requires the ``a2ui-agent`` JS package, which
   *   is not yet published — throws ``A2UINotInstalled`` today.
   * - **flux**: returns an in-tree toolset that advertises the flux
   *   component surface (FluxButton, FluxBadge, FluxCard, …) with
   *   per-component ``llm`` metadata loaded from
   *   ``catalog/flux/catalog.json``. Does *not* require ``a2ui-agent``.
   *
   * Unknown catalog names throw ``A2UIError``.
   */
  static a2ui(opts?: { catalog?: CatalogName | string }): TComposite {
    const catalog = opts?.catalog ?? "basic";
    if (!KNOWN_CATALOGS.includes(catalog as CatalogName)) {
      throw new A2UIError(
        `Unknown catalog ${JSON.stringify(catalog)}. ` +
          `Known catalogs: ${JSON.stringify([...KNOWN_CATALOGS])}`,
      );
    }
    if (catalog === "flux") {
      return _buildFluxA2UIToolset();
    }
    throw new A2UINotInstalled(
      "T.a2ui() requires the 'a2ui-agent' package. " + "Install with: npm install a2ui-agent",
    );
  }

  /**
   * Wrap one or more SKILL.md directories as a SkillToolset for progressive
   * disclosure. Pass a single path, a list of paths, or a list of pre-parsed
   * skill objects. Skill metadata is loaded into the system prompt; full
   * instructions are loaded on demand by the LLM.
   *
   * Mirrors the Python `T.skill(path)` factory.
   */
  static skill(path: string | string[] | unknown[]): TComposite {
    const paths = Array.isArray(path) ? path : [path];
    return new TComposite([
      {
        type: "skill_toolset",
        paths,
      },
    ]);
  }

  // ------------------------------------------------------------------
  // Wrappers
  // ------------------------------------------------------------------

  /** Create a mock tool for testing. */
  static mock(name: string, opts?: { returns?: unknown; sideEffect?: ToolFn }): TComposite {
    return new TComposite([
      {
        type: "mock",
        name,
        returns: opts?.returns,
        sideEffect: opts?.sideEffect,
      },
    ]);
  }

  /** Wrap tool with human confirmation requirement. */
  static confirm(toolOrComposite: TComposite | ToolFn, message?: string): TComposite {
    const items =
      toolOrComposite instanceof TComposite
        ? toolOrComposite.items
        : [{ type: "function", fn: toolOrComposite }];
    return new TComposite(items.map((t) => ({ ...t, confirm: true, confirmMessage: message })));
  }

  /** Wrap tool with timeout. */
  static timeout(toolOrComposite: TComposite | ToolFn, seconds = 30): TComposite {
    const items =
      toolOrComposite instanceof TComposite
        ? toolOrComposite.items
        : [{ type: "function", fn: toolOrComposite }];
    return new TComposite(items.map((t) => ({ ...t, timeout: seconds })));
  }

  /** Wrap tool with TTL-based result cache. */
  static cache(toolOrComposite: TComposite | ToolFn, opts?: { ttl?: number }): TComposite {
    const items =
      toolOrComposite instanceof TComposite
        ? toolOrComposite.items
        : [{ type: "function", fn: toolOrComposite }];
    return new TComposite(items.map((t) => ({ ...t, cache: true, ttl: opts?.ttl ?? 300 })));
  }

  /** Wrap tool with pre/post argument/result transforms. */
  static transform(
    toolOrComposite: TComposite | ToolFn,
    opts: { pre?: ToolFn; post?: ToolFn },
  ): TComposite {
    const items =
      toolOrComposite instanceof TComposite
        ? toolOrComposite.items
        : [{ type: "function", fn: toolOrComposite }];
    return new TComposite(
      items.map((t) => ({ ...t, preTransform: opts.pre, postTransform: opts.post })),
    );
  }
}

// ---------------------------------------------------------------------------
// Flux A2UI toolset — in-tree, no external package dependency
// ---------------------------------------------------------------------------

/**
 * Toolset descriptor emitted by ``T.a2ui({ catalog: "flux" })``.
 *
 * Advertises the flux component surface via a stable shape tests can
 * inspect: ``components`` (sorted flux component names), ``description``
 * (human-readable enumeration), ``llmMetadata`` (per-component
 * ``description`` / ``tags`` / ``examples`` / ``antiPatterns``).
 *
 * This is a data-bearing marker — the ADK-facing runtime integration
 * ships alongside the public ``a2ui-agent[flux]`` package later. Today
 * the marker is enough for ``T.a2ui({ catalog: "flux" })`` to be
 * discoverable and testable.
 */
export interface FluxA2UIToolsetSpec {
  type: "a2ui_flux";
  catalog: "flux";
  components: readonly string[];
  description: string;
  llmMetadata: Record<string, Record<string, unknown>>;
  [key: string]: unknown;
}

function _loadFluxCatalog(): Record<string, unknown> {
  // Walk up from this module until we find catalog/flux/catalog.json.
  const here = dirname(fileURLToPath(import.meta.url));
  // Handle both source layout (ts/src/namespaces) and dist layout
  // (ts/dist/namespaces) — both should reach catalog/flux/catalog.json via
  // relative upward walk since the catalog lives at repo root.
  const candidates = [
    resolve(here, "../../../catalog/flux/catalog.json"),
    resolve(here, "../../../../catalog/flux/catalog.json"),
    resolve(here, "../../../../../catalog/flux/catalog.json"),
  ];
  for (const path of candidates) {
    if (existsSync(path)) {
      try {
        return JSON.parse(readFileSync(path, "utf-8")) as Record<string, unknown>;
      } catch {
        // Fall through to the next candidate if one is corrupt.
      }
    }
  }
  return {};
}

function _buildFluxA2UIToolset(): TComposite {
  const catalog = _loadFluxCatalog();
  const componentsRaw = (catalog.components ?? {}) as Record<
    string,
    { llm?: Record<string, unknown> }
  >;
  const names = Object.keys(componentsRaw).sort();
  const llmMetadata: Record<string, Record<string, unknown>> = {};
  for (const name of names) {
    llmMetadata[name] = (componentsRaw[name]?.llm ?? {}) as Record<string, unknown>;
  }

  const lines: string[] = [
    "A2UI flux catalog toolset — advertises the flux component surface.",
    "",
    "Components:",
  ];
  for (const name of names) {
    const meta = llmMetadata[name] ?? {};
    const desc = typeof meta.description === "string" ? meta.description.split("\n")[0] : "";
    lines.push(`  - ${name}${desc ? `: ${desc}` : ""}`);
  }

  const spec: FluxA2UIToolsetSpec = {
    type: "a2ui_flux",
    catalog: "flux",
    components: Object.freeze(names),
    description: lines.join("\n"),
    llmMetadata,
  };
  return new TComposite([spec]);
}
