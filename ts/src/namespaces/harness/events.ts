/**
 * Event subsystem — typed events, dispatcher, event bus, and session tape.
 *
 * Mirrors `_harness/_events.py`, `_dispatcher.py`, `_event_bus.py`, `_tape.py`.
 *
 * In the Python harness these live in separate files; here they share one
 * module since they form a single observer subsystem and several files
 * would be ~50 lines each.
 */

import { writeFileSync, mkdirSync, readFileSync } from "node:fs";
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
  | "error";

export interface HarnessEventBase {
  kind: HarnessEventKind;
  timestamp: number;
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

export interface GenericEvent extends HarnessEventBase {
  kind: Exclude<HarnessEventKind, TextEvent["kind"] | ToolEvent["kind"] | ModelEvent["kind"]>;
  data?: Record<string, unknown>;
}

export type HarnessEvent = TextEvent | ToolEvent | ModelEvent | GenericEvent;

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

// ─── SessionTape: record/replay events ─────────────────────────────────────

export interface SessionTapeOptions {
  maxEvents?: number;
}

/**
 * Records a sequence of HarnessEvents and can serialize them to JSONL
 * for later replay or audit.
 */
export class SessionTape {
  readonly maxEvents: number;
  readonly events: HarnessEvent[] = [];

  constructor(opts: SessionTapeOptions = {}) {
    this.maxEvents = opts.maxEvents ?? 0;
  }

  record(event: HarnessEvent): void {
    this.events.push(event);
    if (this.maxEvents > 0) {
      while (this.events.length > this.maxEvents) this.events.shift();
    }
  }

  /** Save events as JSONL. */
  save(path: string): void {
    mkdirSync(dirname(path), { recursive: true });
    const lines = this.events.map((e) => JSON.stringify(e)).join("\n");
    writeFileSync(path, lines + "\n", "utf8");
  }

  /** Load events from a JSONL file (replaces any in-memory events). */
  load(path: string): void {
    const text = readFileSync(path, "utf8");
    this.events.length = 0;
    for (const line of text.split("\n")) {
      if (line.trim()) this.events.push(JSON.parse(line));
    }
  }

  /** Replay every recorded event through a subscriber. */
  replay(subscriber: EventSubscriber): void {
    for (const e of this.events) subscriber(e);
  }

  clear(): void {
    this.events.length = 0;
  }
}
