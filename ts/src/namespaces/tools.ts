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
import { A2UIError, A2UINotInstalled } from "../_exceptions.js";
import { KNOWN_CATALOGS, type CatalogName } from "./ui.js";
import * as _toolBuilders from "../builders/tool.js";

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

  // ------------------------------------------------------------------
  // ADK toolset convenience wrappers (Feature #11 parity)
  //
  // These mirror the Python ``T.bigquery`` / ``T.spanner`` / ``T.bigtable`` /
  // ``T.vertex_ai_search`` / ``T.enterprise_search`` / ``T.url_context`` /
  // ``T.computer_use`` factories. ``@google/adk`` (the JS port, 0.6.1) does
  // NOT yet export runtime implementations for these toolsets, so each
  // wrapper lazily constructs the *generated builder shell* from
  // ``../builders/tool.js`` and returns its built config record inside a
  // ``TComposite``. The API surface (and ``.pipe()`` composition) exists
  // today; full runtime functionality lands once ``@google/adk`` ships the
  // corresponding toolset classes. The wrappers are intentionally thin:
  // options pass straight through to the shell's setters.
  // ------------------------------------------------------------------

  /**
   * Wrap ADK ``BigQueryToolset`` (BigQuery data + metadata tools).
   *
   * Constructs the generated ``BigQueryToolset`` builder shell and returns
   * its config record. Credentials / tool config / filters are passed
   * through unchanged. No network or cloud call is made here.
   */
  static bigquery(opts?: {
    credentialsConfig?: unknown;
    bigqueryToolConfig?: unknown;
    toolFilter?: unknown;
  }): TComposite {
    const Cls = _resolveBuilder<typeof _toolBuilders.BigQueryToolset>("BigQueryToolset");
    let b = new Cls();
    if (opts?.credentialsConfig !== undefined) b = b.credentialsConfig(opts.credentialsConfig);
    if (opts?.bigqueryToolConfig !== undefined) b = b.bigqueryToolConfig(opts.bigqueryToolConfig);
    if (opts?.toolFilter !== undefined) b = b.toolFilter(opts.toolFilter);
    return new TComposite([{ type: "toolset", kind: "bigquery", toolset: b.build() }]);
  }

  /**
   * Wrap ADK ``SpannerToolset`` (Spanner data + schema tools).
   *
   * Constructs the generated ``SpannerToolset`` builder shell and returns
   * its config record. Credentials / settings / filters pass through.
   */
  static spanner(opts?: {
    credentialsConfig?: unknown;
    spannerToolSettings?: unknown;
    toolFilter?: unknown;
  }): TComposite {
    const Cls = _resolveBuilder<typeof _toolBuilders.SpannerToolset>("SpannerToolset");
    let b = new Cls();
    if (opts?.credentialsConfig !== undefined) b = b.credentialsConfig(opts.credentialsConfig);
    if (opts?.spannerToolSettings !== undefined) b = b.spannerToolSettings(opts.spannerToolSettings);
    if (opts?.toolFilter !== undefined) b = b.toolFilter(opts.toolFilter);
    return new TComposite([{ type: "toolset", kind: "spanner", toolset: b.build() }]);
  }

  /**
   * Wrap ADK ``BigtableToolset`` (Bigtable data + metadata tools).
   *
   * Constructs the generated ``BigtableToolset`` builder shell and returns
   * its config record. Credentials / settings / filters pass through.
   */
  static bigtable(opts?: {
    credentialsConfig?: unknown;
    bigtableToolSettings?: unknown;
    toolFilter?: unknown;
  }): TComposite {
    const Cls = _resolveBuilder<typeof _toolBuilders.BigtableToolset>("BigtableToolset");
    let b = new Cls();
    if (opts?.credentialsConfig !== undefined) b = b.credentialsConfig(opts.credentialsConfig);
    if (opts?.bigtableToolSettings !== undefined)
      b = b.bigtableToolSettings(opts.bigtableToolSettings);
    if (opts?.toolFilter !== undefined) b = b.toolFilter(opts.toolFilter);
    return new TComposite([{ type: "toolset", kind: "bigtable", toolset: b.build() }]);
  }

  /**
   * Wrap ADK ``VertexAiSearchTool`` (built-in Vertex AI Search grounding).
   *
   * Provide exactly one of ``dataStoreId`` / ``searchEngineId`` /
   * ``dataStoreSpecs``, matching the ADK tool's own validation. Constructs
   * the generated builder shell and returns its config record.
   */
  static vertexAiSearch(opts?: {
    dataStoreId?: string;
    dataStoreSpecs?: unknown;
    searchEngineId?: string;
    filter?: string;
    maxResults?: number;
    bypassMultiToolsLimit?: boolean;
  }): TComposite {
    const Cls = _resolveBuilder<typeof _toolBuilders.VertexAiSearchTool>("VertexAiSearchTool");
    let b = new Cls();
    if (opts?.dataStoreId !== undefined) b = b.dataStoreId(opts.dataStoreId);
    if (opts?.dataStoreSpecs !== undefined) b = b.dataStoreSpecs(opts.dataStoreSpecs);
    if (opts?.searchEngineId !== undefined) b = b.searchEngineId(opts.searchEngineId);
    if (opts?.filter !== undefined) b = b.filter(opts.filter);
    if (opts?.maxResults !== undefined) b = b.maxResults(opts.maxResults);
    if (opts?.bypassMultiToolsLimit !== undefined)
      b = b.bypassMultiToolsLimit(opts.bypassMultiToolsLimit);
    return new TComposite([{ type: "toolset", kind: "vertex_ai_search", toolset: b.build() }]);
  }

  /** Alias for {@link T.vertexAiSearch}, matching the feature-spec name. */
  static vertexSearch(opts?: {
    dataStoreId?: string;
    dataStoreSpecs?: unknown;
    searchEngineId?: string;
    filter?: string;
    maxResults?: number;
    bypassMultiToolsLimit?: boolean;
  }): TComposite {
    return T.vertexAiSearch(opts);
  }

  /**
   * Wrap ADK ``EnterpriseWebSearchTool`` (Gemini 2+ enterprise web grounding).
   *
   * A built-in tool with no constructor arguments. Constructs the generated
   * builder shell and returns its config record.
   */
  static enterpriseSearch(): TComposite {
    const Cls = _resolveBuilder<typeof _toolBuilders.EnterpriseWebSearchTool>(
      "EnterpriseWebSearchTool",
    );
    return new TComposite([
      { type: "toolset", kind: "enterprise_search", toolset: new Cls().build() },
    ]);
  }

  /**
   * Wrap ADK ``UrlContextTool`` (Gemini 2 automatic URL content retrieval).
   *
   * A built-in tool with no constructor arguments. Constructs the generated
   * builder shell and returns its config record.
   */
  static urlContext(): TComposite {
    const Cls = _resolveBuilder<typeof _toolBuilders.UrlContextTool>("UrlContextTool");
    return new TComposite([{ type: "toolset", kind: "url_context", toolset: new Cls().build() }]);
  }

  /**
   * Wrap ADK ``ComputerUseToolset`` (screen-control function tools).
   *
   * @param computer A ``BaseComputer`` implementation (or its identifier)
   *   that performs the actual screen/keyboard/mouse actions. Passed through
   *   to the generated builder shell's constructor unchanged.
   */
  static computerUse(
    computer: unknown,
    _opts?: { excludedPredefinedFunctions?: string[] },
  ): TComposite {
    const Cls = _resolveBuilder<typeof _toolBuilders.ComputerUseToolset>("ComputerUseToolset");
    // The generated shell types ``computer`` as a string; pass through any
    // BaseComputer-like value unchanged for forward compatibility.
    const built = new Cls(computer as string).build();
    return new TComposite([{ type: "toolset", kind: "computer_use", toolset: built }]);
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

// ---------------------------------------------------------------------------
// ADK toolset shell construction (Feature #11 parity)
// ---------------------------------------------------------------------------

/**
 * Lazily resolve a generated builder shell class by name from
 * ``../builders/tool.js``.
 *
 * The builder classes are bundled with this package (not ``@google/adk``),
 * so resolution never touches the network or cloud. Construction of the
 * resolved class is deferred to the caller — this is the meaningful
 * laziness: the shell is only built when the ``T.*`` factory is invoked.
 *
 * Throws a clear error if the named builder is unexpectedly absent (e.g. a
 * future codegen change drops the shell), so callers fail loudly rather than
 * silently producing an empty composite.
 */
function _resolveBuilder<C>(name: string): C {
  const registry = _toolBuilders as unknown as Record<string, unknown>;
  const Cls = registry[name];
  if (typeof Cls !== "function") {
    throw new Error(
      `T toolset wrapper could not resolve generated builder '${name}'. ` +
        `Expected an export from '../builders/tool.js'. This indicates a ` +
        `codegen/version mismatch.`,
    );
  }
  return Cls as C;
}
