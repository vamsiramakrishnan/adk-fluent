/**
 * Event subsystem — typed events, dispatcher, event bus, and session tape.
 *
 * Mirrors `_harness/_events.py`, `_dispatcher.py`, `_event_bus.py`,
 * `_session/_tape.py`, `_session/_tape_backend.py`.
 *
 * In the Python harness these live in separate files; here they share one
 * module since they form a single observer subsystem.
 *
 * The tape stamps every recorded event with a monotonic `seq` so
 * downstream consumers (reactors, streams, replays) can resume from a
 * cursor instead of rebuilding history from scratch. `since(n)` walks
 * the buffered prefix synchronously; `tail(fromSeq)` is an async
 * iterator that follows live writes. Backends (InMemory, JSONL, Null,
 * Chain) are pluggable via the `TapeBackend` interface.
 */

import { appendFileSync, writeFileSync, mkdirSync, readFileSync, existsSync } from "node:fs";
import { dirname } from "node:path";

// ─── event shapes ──────────────────────────────────────────────────────────

export type HarnessEventKind =
  | "session_start"
  | "session_end"
  | "turn_start"
  | "turn_end"
  | "text"
  | "tool_call_start"
  | "tool_call_end"
  | "tool_call_error"
  | "model_call_start"
  | "model_call_end"
  | "compression"
  | "approval_request"
  | "approval_response"
  | "interrupt"
  | "error"
  // Workflow lifecycle (Phase C).
  | "step_started"
  | "step_completed"
  | "iteration_started"
  | "iteration_completed"
  | "branch_started"
  | "branch_completed"
  | "subagent_started"
  | "subagent_completed"
  | "attempt_failed"
  // Reactor + signal plumbing (Phase F).
  | "signal_changed";

export interface HarnessEventBase {
  kind: HarnessEventKind;
  timestamp: number;
  /**
   * Monotonic per-session sequence number. Assigned by `SessionTape`
   * at record time; undefined until the event is written to a tape.
   * Consumers should prefer `EventRecord` when they need `seq` to be
   * present.
   */
  seq?: number;
}

export interface TextEvent extends HarnessEventBase {
  kind: "text";
  text: string;
}

export interface ToolEvent extends HarnessEventBase {
  kind: "tool_call_start" | "tool_call_end" | "tool_call_error";
  toolName: string;
  args?: Record<string, unknown>;
  result?: unknown;
  durationMs?: number;
  error?: string;
}

export interface ModelEvent extends HarnessEventBase {
  kind: "model_call_start" | "model_call_end";
  model?: string;
  inputTokens?: number;
  outputTokens?: number;
}

export interface StepLifecycleEvent extends HarnessEventBase {
  kind: "step_started" | "step_completed";
  agentName: string;
  agentType?: string;
  parentName?: string;
  ok?: boolean;
  error?: string;
}

export interface IterationLifecycleEvent extends HarnessEventBase {
  kind: "iteration_started" | "iteration_completed";
  loopName: string;
  iteration: number;
  ok?: boolean;
}

export interface BranchLifecycleEvent extends HarnessEventBase {
  kind: "branch_started" | "branch_completed";
  fanoutName: string;
  branchName: string;
  ok?: boolean;
  error?: string;
}

export interface SubagentLifecycleEvent extends HarnessEventBase {
  kind: "subagent_started" | "subagent_completed";
  role: string;
  prompt?: string;
  output?: string;
  isError?: boolean;
  error?: string;
}

export interface AttemptFailedEvent extends HarnessEventBase {
  kind: "attempt_failed";
  agentName: string;
  attempt: number;
  error: string;
}

export interface SignalChangedEvent extends HarnessEventBase {
  kind: "signal_changed";
  name: string;
  version: number;
  value: unknown;
  previous: unknown;
}

export interface GenericEvent extends HarnessEventBase {
  kind: Exclude<
    HarnessEventKind,
    | TextEvent["kind"]
    | ToolEvent["kind"]
    | ModelEvent["kind"]
    | StepLifecycleEvent["kind"]
    | IterationLifecycleEvent["kind"]
    | BranchLifecycleEvent["kind"]
    | SubagentLifecycleEvent["kind"]
    | AttemptFailedEvent["kind"]
    | SignalChangedEvent["kind"]
  >;
  data?: Record<string, unknown>;
}

export type HarnessEvent =
  | TextEvent
  | ToolEvent
  | ModelEvent
  | StepLifecycleEvent
  | IterationLifecycleEvent
  | BranchLifecycleEvent
  | SubagentLifecycleEvent
  | AttemptFailedEvent
  | SignalChangedEvent
  | GenericEvent;

/** An event that has been recorded and therefore carries a `seq`. */
export type EventRecord = HarnessEvent & { seq: number };

export type EventSubscriber = (event: HarnessEvent) => void;

// ─── EventDispatcher: subscribe by kind ────────────────────────────────────

/**
 * Lightweight pub/sub keyed on event kind. The dispatcher is the
 * canonical translation layer from runtime events into HarnessEvents.
 */
export class EventDispatcher {
  private readonly listeners = new Map<HarnessEventKind | "*", EventSubscriber[]>();

  on(kind: HarnessEventKind | "*", fn: EventSubscriber): this {
    let bucket = this.listeners.get(kind);
    if (!bucket) {
      bucket = [];
      this.listeners.set(kind, bucket);
    }
    bucket.push(fn);
    return this;
  }

  emit(event: HarnessEvent): void {
    for (const fn of this.listeners.get(event.kind) ?? []) fn(event);
    for (const fn of this.listeners.get("*") ?? []) fn(event);
  }

  /** Subscribe a subscriber to ALL events. */
  subscribe(fn: EventSubscriber): this {
    return this.on("*", fn);
  }

  clear(): void {
    this.listeners.clear();
  }
}

// ─── EventBus: dispatcher + retained history + lifecycle helpers ───────────

export interface EventBusOptions {
  maxBuffer?: number;
}

/**
 * Session-scoped typed event backbone. Wraps an EventDispatcher and
 * optionally retains the last N events. Other harness modules
 * (renderer, tape, hooks) subscribe to the bus instead of building
 * their own observation layers.
 */
export class EventBus extends EventDispatcher {
  readonly maxBuffer: number;
  readonly history: HarnessEvent[] = [];

  constructor(opts: EventBusOptions = {}) {
    super();
    this.maxBuffer = opts.maxBuffer ?? 0;
  }

  override emit(event: HarnessEvent): void {
    super.emit(event);
    if (this.maxBuffer > 0) {
      this.history.push(event);
      while (this.history.length > this.maxBuffer) this.history.shift();
    }
  }

  /** Create a SessionTape pre-subscribed to this bus. */
  tape(opts: SessionTapeOptions = {}): SessionTape {
    const t = new SessionTape(opts);
    this.subscribe((e) => t.record(e));
    return t;
  }

  /** Build a before-tool callback that emits `tool_call_start`. */
  beforeToolHook(): (toolName: string, args: Record<string, unknown>) => void {
    return (toolName, args) => {
      this.emit({ kind: "tool_call_start", toolName, args, timestamp: Date.now() });
    };
  }

  /** Build an after-tool callback that emits `tool_call_end`. */
  afterToolHook(): (toolName: string, result: unknown) => void {
    return (toolName, result) => {
      this.emit({ kind: "tool_call_end", toolName, result, timestamp: Date.now() });
    };
  }
}

// ─── TapeBackend — pluggable persistence for SessionTape ──────────────────

/**
 * Pluggable persistence target for `SessionTape`. Implementations can
 * mirror the tape to disk, a remote queue, or nothing at all.
 *
 * The tape always keeps its own in-memory deque; the backend is
 * write-through. Reads (`since`, `tail`) are served from the tape's
 * buffer, not the backend, so durability doesn't pay a read tax.
 */
export interface TapeBackend {
  /** Persist a single recorded event. Must not throw for routine writes. */
  append(event: EventRecord): void;
  /** Flush any buffered writes. No-op for backends that write eagerly. */
  flush?(): void;
  /** Close the backend (e.g. release file handles). */
  close?(): void;
}

/** Default backend — writes to nowhere. */
export class NullBackend implements TapeBackend {
  append(_event: EventRecord): void {
    // no-op
  }
}

/**
 * In-memory backend. Useful for tests that want to assert what the
 * tape would have persisted without touching disk.
 */
export class InMemoryBackend implements TapeBackend {
  readonly entries: EventRecord[] = [];
  append(event: EventRecord): void {
    this.entries.push(event);
  }
  clear(): void {
    this.entries.length = 0;
  }
}

export interface JsonlBackendOptions {
  /** Path to the JSONL file. Parent directories are created as needed. */
  path: string;
  /** Truncate the file on construction. Default: false (append-only). */
  truncate?: boolean;
}

/** Append-only JSONL file backend. One event per line. */
export class JsonlBackend implements TapeBackend {
  readonly path: string;

  constructor(opts: JsonlBackendOptions) {
    this.path = opts.path;
    mkdirSync(dirname(this.path), { recursive: true });
    if (opts.truncate || !existsSync(this.path)) {
      writeFileSync(this.path, "", "utf8");
    }
  }

  append(event: EventRecord): void {
    appendFileSync(this.path, JSON.stringify(event) + "\n", "utf8");
  }
}

/** Fan an event out to multiple backends. First wins on exceptions. */
export class ChainBackend implements TapeBackend {
  readonly backends: TapeBackend[];
  constructor(backends: TapeBackend[]) {
    this.backends = backends;
  }
  append(event: EventRecord): void {
    for (const b of this.backends) b.append(event);
  }
  flush(): void {
    for (const b of this.backends) b.flush?.();
  }
  close(): void {
    for (const b of this.backends) b.close?.();
  }
}

// ─── SessionTape: record/replay events with seq + cursor + tail ───────────

export interface SessionTapeOptions {
  maxEvents?: number;
  backend?: TapeBackend;
}

type TailWaiter = () => void;

/**
 * Records a sequence of HarnessEvents and can serialize them to JSONL
 * for later replay or audit. Every recorded event is stamped with a
 * monotonic `seq`; consumers can resume from a cursor via `since(seq)`
 * (synchronous prefix drain) or `tail(fromSeq)` (async live follow).
 */
export class SessionTape {
  readonly maxEvents: number;
  readonly events: EventRecord[] = [];
  readonly backend: TapeBackend;
  private _nextSeq = 0;
  private readonly _waiters: TailWaiter[] = [];

  constructor(opts: SessionTapeOptions = {}) {
    this.maxEvents = opts.maxEvents ?? 0;
    this.backend = opts.backend ?? new NullBackend();
  }

  /** Sequence number that would be assigned to the *next* event. */
  get head(): number {
    return this._nextSeq;
  }

  /**
   * Append an event. Returns the recorded version with `seq` populated.
   * The tape mutates the input object with the assigned `seq` so
   * downstream subscribers can read it from their copy too.
   */
  record(event: HarnessEvent): EventRecord {
    const seq = this._nextSeq++;
    (event as EventRecord).seq = seq;
    const record = event as EventRecord;
    this.events.push(record);
    if (this.maxEvents > 0) {
      while (this.events.length > this.maxEvents) this.events.shift();
    }
    try {
      this.backend.append(record);
    } catch {
      // backend failures must not block the tape
    }
    // wake any tail() async iterators parked on the condition
    if (this._waiters.length > 0) {
      const waiters = this._waiters.splice(0);
      for (const w of waiters) w();
    }
    return record;
  }

  /** Iterate over recorded events whose seq is ≥ `fromSeq`. */
  *since(fromSeq = 0): Iterable<EventRecord> {
    for (const e of this.events) {
      if ((e.seq ?? 0) >= fromSeq) yield e;
    }
  }

  /**
   * Follow the tape asynchronously starting at `fromSeq`. Yields events
   * as they are recorded. The iterator is open-ended — callers must
   * break out themselves (e.g. via an `AbortSignal`) when done.
   */
  async *tail(fromSeq = 0, opts: { signal?: AbortSignal } = {}): AsyncIterable<EventRecord> {
    let cursor = fromSeq;
    while (true) {
      for (const e of this.events) {
        if ((e.seq ?? 0) >= cursor) {
          yield e;
          cursor = (e.seq ?? 0) + 1;
        }
      }
      if (opts.signal?.aborted) return;
      await new Promise<void>((resolve) => {
        const done = () => {
          cleanup();
          resolve();
        };
        const onAbort = () => {
          cleanup();
          resolve();
        };
        const cleanup = () => {
          opts.signal?.removeEventListener("abort", onAbort);
          const idx = this._waiters.indexOf(done);
          if (idx >= 0) this._waiters.splice(idx, 1);
        };
        this._waiters.push(done);
        opts.signal?.addEventListener("abort", onAbort, { once: true });
      });
      if (opts.signal?.aborted) return;
    }
  }

  /** Filter events by kind. */
  filter(kind: HarnessEventKind): EventRecord[] {
    return this.events.filter((e) => e.kind === kind);
  }

  /** Save events as JSONL. */
  save(path: string): void {
    mkdirSync(dirname(path), { recursive: true });
    const lines = this.events.map((e) => JSON.stringify(e)).join("\n");
    writeFileSync(path, lines + (this.events.length > 0 ? "\n" : ""), "utf8");
  }

  /**
   * Load events from a JSONL file (replaces any in-memory events).
   * Missing `seq` fields are backfilled from the line index so
   * pre-seq tapes still load cleanly.
   */
  load(path: string): void {
    const text = readFileSync(path, "utf8");
    this.events.length = 0;
    this._nextSeq = 0;
    let lineIdx = 0;
    for (const line of text.split("\n")) {
      if (!line.trim()) continue;
      const entry = JSON.parse(line) as HarnessEvent;
      const seq = typeof entry.seq === "number" ? entry.seq : lineIdx;
      (entry as EventRecord).seq = seq;
      this.events.push(entry as EventRecord);
      if (seq >= this._nextSeq) this._nextSeq = seq + 1;
      lineIdx++;
    }
  }

  /** Replay every recorded event through a subscriber. */
  replay(subscriber: EventSubscriber): void {
    for (const e of this.events) subscriber(e);
  }

  clear(): void {
    this.events.length = 0;
    this._nextSeq = 0;
  }

  /** Count of events grouped by kind. Handy for assertions. */
  summary(): Record<string, number> {
    const out: Record<string, number> = {};
    for (const e of this.events) {
      out[e.kind] = (out[e.kind] ?? 0) + 1;
    }
    return out;
  }

  get size(): number {
    return this.events.length;
  }
}
