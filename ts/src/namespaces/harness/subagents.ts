/**
 * Dynamic subagent spawner + task-tool factory.
 *
 * Mirrors `python/src/adk_fluent/_subagents/`. The parent LLM keeps
 * control of the conversation and, when it needs focused work done,
 * calls a `task(role, prompt)` tool that dispatches a fresh specialist,
 * waits for the answer, and folds the result back into the parent's
 * context window.
 *
 * A subagent is **not** a long-running teammate — it is a short-lived
 * worker with its own instruction, its own toolset, and a disposable
 * context. The parent never sees the specialist's scratchpad, only its
 * final output.
 *
 * This module is intentionally **not** coupled to `@google/adk` — the
 * runtime contract is a plain `run(spec, prompt, context?) =>
 * SubagentResult` callable. That keeps it unit-testable in isolation
 * and lets callers plug in a local runner, an A2A endpoint, or canned
 * responses in tests.
 */

/**
 * Declarative description of one dynamically-spawned specialist.
 *
 * Specs are immutable value objects so they can be shared across
 * registries and cached without defensive copies. Construct via the
 * options-object constructor or via `H.subagentSpec(...)`.
 */
export interface SubagentSpecOptions {
  /** Short, stable identifier (`"researcher"`, `"reviewer"`). */
  role: string;
  /** System prompt / role description handed to the specialist. */
  instruction: string;
  /** One-line human description surfaced in the task tool docstring. */
  description?: string;
  /** Optional model override; `undefined` inherits the runner's default. */
  model?: string;
  /** Tool names the specialist may call. The runner resolves names. */
  toolNames?: readonly string[];
  /** One of the `PermissionMode` constants; defaults to `"default"`. */
  permissionMode?: string;
  /** Optional per-invocation token ceiling. */
  maxTokens?: number;
  /** Free-form runner-specific metadata. */
  metadata?: Record<string, unknown>;
}

export class SubagentSpec {
  readonly role: string;
  readonly instruction: string;
  readonly description: string;
  readonly model: string | undefined;
  readonly toolNames: readonly string[];
  readonly permissionMode: string;
  readonly maxTokens: number | undefined;
  readonly metadata: Readonly<Record<string, unknown>>;

  constructor(options: SubagentSpecOptions) {
    if (!options.role) {
      throw new Error("SubagentSpec.role must be a non-empty string");
    }
    if (!options.instruction) {
      throw new Error("SubagentSpec.instruction must be a non-empty string");
    }
    this.role = options.role;
    this.instruction = options.instruction;
    this.description = options.description ?? "";
    this.model = options.model;
    this.toolNames = Object.freeze([...(options.toolNames ?? [])]);
    this.permissionMode = options.permissionMode ?? "default";
    this.maxTokens = options.maxTokens;
    this.metadata = Object.freeze({ ...(options.metadata ?? {}) });
    Object.freeze(this);
  }
}

/**
 * Structured output from a subagent run.
 *
 * Results are immutable. Errors populate the `error` field and set
 * `isError = true`; callers use `toToolOutput()` to render the canonical
 * `[role] output` or `[role:error] reason` string returned from the
 * task tool.
 */
export interface SubagentResultOptions {
  role: string;
  output: string;
  usage?: Record<string, number>;
  artifacts?: Record<string, unknown>;
  metadata?: Record<string, unknown>;
  error?: string;
}

export class SubagentResult {
  readonly role: string;
  readonly output: string;
  readonly usage: Readonly<Record<string, number>>;
  readonly artifacts: Readonly<Record<string, unknown>>;
  readonly metadata: Readonly<Record<string, unknown>>;
  readonly error: string;

  constructor(options: SubagentResultOptions) {
    this.role = options.role;
    this.output = options.output;
    this.usage = Object.freeze({ ...(options.usage ?? {}) });
    this.artifacts = Object.freeze({ ...(options.artifacts ?? {}) });
    this.metadata = Object.freeze({ ...(options.metadata ?? {}) });
    this.error = options.error ?? "";
    Object.freeze(this);
  }

  get isError(): boolean {
    return this.error.length > 0;
  }

  /**
   * Render the canonical tool-output string. Errors surface as
   * `[role:error] reason`; successful runs prefix the role name so the
   * parent LLM can reason about provenance.
   */
  toToolOutput(): string {
    if (this.isError) {
      return `[${this.role}:error] ${this.error}`;
    }
    return `[${this.role}] ${this.output}`;
  }
}

/**
 * Ordered catalogue of specs keyed by role. Not thread-safe — registries
 * are populated at construction time, before any invocation runs.
 */
export class SubagentRegistry {
  private readonly specs: Map<string, SubagentSpec>;

  constructor(specs?: Iterable<SubagentSpec>) {
    this.specs = new Map();
    if (specs) {
      for (const spec of specs) {
        this.register(spec);
      }
    }
  }

  /** Register a new spec. Throws if the role is already registered. */
  register(spec: SubagentSpec): void {
    if (this.specs.has(spec.role)) {
      throw new Error(
        `Subagent role '${spec.role}' is already registered; use .replace() to overwrite.`,
      );
    }
    this.specs.set(spec.role, spec);
  }

  /** Register `spec`, overwriting any existing entry with the same role. */
  replace(spec: SubagentSpec): void {
    this.specs.set(spec.role, spec);
  }

  /** Remove the spec for `role`. Silent no-op if absent. */
  unregister(role: string): void {
    this.specs.delete(role);
  }

  /** Return the spec for `role` or `undefined` if not registered. */
  get(role: string): SubagentSpec | undefined {
    return this.specs.get(role);
  }

  /** Return the spec for `role` or throw if not registered. */
  require(role: string): SubagentSpec {
    const spec = this.specs.get(role);
    if (!spec) {
      const known = [...this.specs.keys()].sort().join(", ");
      throw new Error(
        `Unknown subagent role '${role}'. Known roles: ${known || "(none)"}`,
      );
    }
    return spec;
  }

  /** Registered role names in insertion order. */
  roles(): string[] {
    return [...this.specs.keys()];
  }

  get size(): number {
    return this.specs.size;
  }

  has(role: string): boolean {
    return this.specs.has(role);
  }

  [Symbol.iterator](): IterableIterator<SubagentSpec> {
    return this.specs.values();
  }

  /**
   * Render a human-readable roster of all registered specialists, used
   * by `makeTaskTool` to build the task-tool docstring so the parent
   * LLM can pick a role.
   */
  roster(): string {
    if (this.specs.size === 0) {
      return "(no subagents registered)";
    }
    const lines: string[] = [];
    for (const spec of this.specs.values()) {
      const fallback = spec.instruction.split("\n")[0] ?? "";
      const desc = spec.description || fallback;
      lines.push(`- ${spec.role}: ${desc}`);
    }
    return lines.join("\n");
  }
}

/**
 * Runtime contract: synchronous subagent execution.
 *
 * Runners receive a spec, a per-call prompt, and an optional context
 * dict (the state the parent exposes). They must return a fully
 * populated `SubagentResult`. Runners that need async execution should
 * wrap the event loop internally; the task tool never awaits.
 */
export interface SubagentRunner {
  run(
    spec: SubagentSpec,
    prompt: string,
    context?: Record<string, unknown>,
  ): SubagentResult;
}

export class SubagentRunnerError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "SubagentRunnerError";
  }
}

type Responder = (
  spec: SubagentSpec,
  prompt: string,
  context?: Record<string, unknown>,
) => string;

export interface FakeSubagentRunnerOptions {
  /** Invoked per run; defaults to echoing the prompt. */
  responder?: Responder;
  /** Fixed usage dict attached to every result. */
  usage?: Record<string, number>;
  /** Role → error string for simulating per-role failures. */
  errorForRole?: Record<string, string>;
}

/** Recorded call entry captured by `FakeSubagentRunner`. */
export interface SubagentCall {
  spec: SubagentSpec;
  prompt: string;
  context: Record<string, unknown> | undefined;
}

/**
 * Deterministic runner used by tests and local sandboxes.
 *
 * By default echoes the prompt. Supply `responder` for custom output,
 * `errorForRole` to simulate failures per role, and `usage` to attach
 * a fixed usage dict to every result. Every invocation is recorded in
 * the `.calls` audit log.
 */
export class FakeSubagentRunner implements SubagentRunner {
  private readonly responder: Responder;
  private readonly fixedUsage: Record<string, number>;
  private readonly errors: Record<string, string>;
  private readonly log: SubagentCall[] = [];

  constructor(options: FakeSubagentRunnerOptions = {}) {
    this.responder =
      options.responder ?? ((_spec, prompt) => `echo: ${prompt}`);
    this.fixedUsage = { ...(options.usage ?? {}) };
    this.errors = { ...(options.errorForRole ?? {}) };
  }

  /** Return the call log in invocation order. */
  get calls(): readonly SubagentCall[] {
    return [...this.log];
  }

  run(
    spec: SubagentSpec,
    prompt: string,
    context?: Record<string, unknown>,
  ): SubagentResult {
    this.log.push({ spec, prompt, context });
    if (spec.role in this.errors) {
      return new SubagentResult({
        role: spec.role,
        output: "",
        usage: { ...this.fixedUsage },
        error: this.errors[spec.role],
      });
    }
    try {
      const output = this.responder(spec, prompt, context);
      return new SubagentResult({
        role: spec.role,
        output: String(output),
        usage: { ...this.fixedUsage },
      });
    } catch (exc) {
      const reason = exc instanceof Error ? exc.message : String(exc);
      return new SubagentResult({
        role: spec.role,
        output: "",
        usage: { ...this.fixedUsage },
        error: `Subagent responder raised: ${reason}`,
      });
    }
  }
}

/**
 * Task-tool callable with a human-readable docstring enumerating the
 * available subagent roles. The parent LLM calls this with a role name
 * and a prompt; the tool dispatches to the runner and returns the
 * canonical `[role] output` string.
 */
export interface TaskTool {
  (role: string, prompt: string): string;
  /** Name the tool function is exposed under. */
  toolName: string;
  /** Full docstring enumerating the registered roles. */
  description: string;
}

export interface MakeTaskToolOptions {
  /**
   * Optional callable returning the context dict to pass into the
   * runner on every invocation. Use this to thread the parent agent's
   * state into subagents.
   */
  contextProvider?: () => Record<string, unknown>;
  /** Identifier the tool function is exposed under. Defaults to `"task"`. */
  toolName?: string;
}

/**
 * Build a `task(role, prompt) => string` callable backed by the
 * registry and runner. The returned function's `description` property
 * enumerates every registered role with its description so the parent
 * LLM sees an accurate menu.
 */
export function makeTaskTool(
  registry: SubagentRegistry,
  runner: SubagentRunner,
  options: MakeTaskToolOptions = {},
): TaskTool {
  const toolName = options.toolName ?? "task";
  const contextProvider = options.contextProvider;

  const task = ((role: string, prompt: string): string => {
    const spec = registry.get(role);
    if (!spec) {
      const known = registry.roles().join(", ") || "(none)";
      return `Error: unknown subagent role '${role}'. Known roles: ${known}`;
    }
    const context = contextProvider ? contextProvider() : undefined;
    try {
      const result = runner.run(spec, prompt, context);
      return result.toToolOutput();
    } catch (exc) {
      const reason = exc instanceof Error ? exc.message : String(exc);
      return `[${role}:error] Runner raised: ${reason}`;
    }
  }) as TaskTool;

  task.toolName = toolName;
  task.description =
    "Spawn a subagent specialist to handle a sub-task.\n\n" +
    "Args:\n" +
    "    role: The specialist to invoke. Must be one of the roles below.\n" +
    "    prompt: The task description to hand to the specialist.\n\n" +
    "Available roles:\n" +
    `${registry.roster()}\n`;

  // Expose the tool name via Function.name for parity with
  // `task.__name__` in Python — defineProperty lets us override the
  // normally-readonly `name` slot.
  Object.defineProperty(task, "name", { value: toolName, configurable: true });

  return task;
}
