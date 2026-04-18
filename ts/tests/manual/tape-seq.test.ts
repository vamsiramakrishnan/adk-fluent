/**
 * Phase A + B: SessionTape seq/cursor/tail + pluggable backends.
 *
 * Mirrors python/tests/manual/test_tape_seq.py, test_tape_tail.py,
 * test_tape_backend.py.
 */

import { describe, expect, it } from "vitest";
import { mkdtempSync, readFileSync, writeFileSync, existsSync } from "node:fs";
import { join } from "node:path";
import { tmpdir } from "node:os";

import {
  SessionTape,
  InMemoryBackend,
  JsonlBackend,
  NullBackend,
  ChainBackend,
  type HarnessEvent,
  type EventRecord,
} from "../../src/namespaces/harness/events.js";

function makeEvent(text: string): HarnessEvent {
  return { kind: "text", text, timestamp: Date.now() };
}

describe("SessionTape — seq + cursor", () => {
  it("stamps monotonic seq on every recorded event", () => {
    const tape = new SessionTape();
    const a = tape.record(makeEvent("a"));
    const b = tape.record(makeEvent("b"));
    const c = tape.record(makeEvent("c"));
    expect(a.seq).toBe(0);
    expect(b.seq).toBe(1);
    expect(c.seq).toBe(2);
    expect(tape.head).toBe(3);
  });

  it("since(fromSeq) yields only records at or after the cursor", () => {
    const tape = new SessionTape();
    for (let i = 0; i < 5; i++) tape.record(makeEvent(`e${i}`));
    const tail = [...tape.since(2)].map((e) => (e as { text: string }).text);
    expect(tail).toEqual(["e2", "e3", "e4"]);
  });

  it("since(0) returns all records", () => {
    const tape = new SessionTape();
    tape.record(makeEvent("x"));
    tape.record(makeEvent("y"));
    expect([...tape.since()].length).toBe(2);
  });

  it("head advances on record; stays fixed on read", () => {
    const tape = new SessionTape();
    expect(tape.head).toBe(0);
    tape.record(makeEvent("x"));
    expect(tape.head).toBe(1);
    // Reading shouldn't move head.
    const drained = [...tape.since(0)];
    expect(drained.length).toBe(1);
    expect(tape.head).toBe(1);
  });

  it("clear() resets head and events", () => {
    const tape = new SessionTape();
    tape.record(makeEvent("x"));
    tape.record(makeEvent("y"));
    tape.clear();
    expect(tape.head).toBe(0);
    expect(tape.size).toBe(0);
  });

  it("load backfills seq from line index for pre-seq tapes", () => {
    const dir = mkdtempSync(join(tmpdir(), "tape-"));
    const path = join(dir, "legacy.jsonl");
    // Pretend these were written without seq fields.
    const lines = [
      JSON.stringify({ kind: "text", text: "a", timestamp: 1 }),
      JSON.stringify({ kind: "text", text: "b", timestamp: 2 }),
      JSON.stringify({ kind: "text", text: "c", timestamp: 3 }),
    ].join("\n");
    writeFileSync(path, lines + "\n", "utf8");
    const tape = new SessionTape();
    tape.load(path);
    expect(tape.events.map((e) => e.seq)).toEqual([0, 1, 2]);
    expect(tape.head).toBe(3);
  });

  it("save/load round-trips seq values", () => {
    const dir = mkdtempSync(join(tmpdir(), "tape-"));
    const path = join(dir, "tape.jsonl");
    const tape = new SessionTape();
    tape.record(makeEvent("a"));
    tape.record(makeEvent("b"));
    tape.save(path);
    const reloaded = new SessionTape();
    reloaded.load(path);
    expect(reloaded.events.map((e) => e.seq)).toEqual([0, 1]);
    expect(reloaded.head).toBe(2);
  });

  it("summary() counts events grouped by kind", () => {
    const tape = new SessionTape();
    tape.record({ kind: "text", text: "a", timestamp: 0 });
    tape.record({ kind: "text", text: "b", timestamp: 0 });
    tape.record({
      kind: "tool_call_start",
      toolName: "bash",
      timestamp: 0,
    });
    expect(tape.summary()).toEqual({ text: 2, tool_call_start: 1 });
  });
});

describe("SessionTape — tail() async iterator", () => {
  it("yields events as they arrive", async () => {
    const tape = new SessionTape();
    const collected: string[] = [];

    const run = async () => {
      for await (const e of tape.tail(0)) {
        collected.push((e as { text: string }).text);
        if (collected.length === 3) return;
      }
    };
    const done = run();

    tape.record(makeEvent("a"));
    tape.record(makeEvent("b"));
    tape.record(makeEvent("c"));
    await done;

    expect(collected).toEqual(["a", "b", "c"]);
  });

  it("resumes from a cursor", async () => {
    const tape = new SessionTape();
    tape.record(makeEvent("a"));
    tape.record(makeEvent("b"));

    const collected: string[] = [];
    const run = async () => {
      for await (const e of tape.tail(1)) {
        collected.push((e as { text: string }).text);
        if (collected.length === 2) return;
      }
    };
    const done = run();
    tape.record(makeEvent("c"));
    await done;

    expect(collected).toEqual(["b", "c"]);
  });

  it("stops cleanly on AbortSignal", async () => {
    const tape = new SessionTape();
    const ctrl = new AbortController();
    const collected: EventRecord[] = [];
    const done = (async () => {
      for await (const e of tape.tail(0, { signal: ctrl.signal })) {
        collected.push(e);
      }
    })();
    tape.record(makeEvent("x"));
    // allow the yield to happen
    await new Promise((r) => setTimeout(r, 5));
    ctrl.abort();
    await done;
    expect(collected.length).toBe(1);
  });
});

describe("TapeBackend — pluggable persistence", () => {
  it("NullBackend is a no-op", () => {
    const backend = new NullBackend();
    const tape = new SessionTape({ backend });
    tape.record(makeEvent("x"));
    expect(tape.size).toBe(1);
  });

  it("InMemoryBackend mirrors every recorded event", () => {
    const backend = new InMemoryBackend();
    const tape = new SessionTape({ backend });
    tape.record(makeEvent("a"));
    tape.record(makeEvent("b"));
    expect(backend.entries.map((e) => (e as { text: string }).text)).toEqual(["a", "b"]);
    expect(backend.entries.map((e) => e.seq)).toEqual([0, 1]);
  });

  it("JsonlBackend writes one event per line", () => {
    const dir = mkdtempSync(join(tmpdir(), "tape-"));
    const path = join(dir, "out.jsonl");
    const backend = new JsonlBackend({ path });
    const tape = new SessionTape({ backend });
    tape.record(makeEvent("a"));
    tape.record(makeEvent("b"));
    expect(existsSync(path)).toBe(true);
    const lines = readFileSync(path, "utf8").trim().split("\n");
    expect(lines.length).toBe(2);
    expect(JSON.parse(lines[0]!).text).toBe("a");
    expect(JSON.parse(lines[1]!).seq).toBe(1);
  });

  it("JsonlBackend truncates when requested", () => {
    const dir = mkdtempSync(join(tmpdir(), "tape-"));
    const path = join(dir, "out.jsonl");
    new JsonlBackend({ path }).append({ kind: "text", text: "stale", timestamp: 0, seq: 0 });
    new JsonlBackend({ path, truncate: true }); // truncate
    expect(readFileSync(path, "utf8")).toBe("");
  });

  it("ChainBackend fans out to multiple backends", () => {
    const a = new InMemoryBackend();
    const b = new InMemoryBackend();
    const tape = new SessionTape({ backend: new ChainBackend([a, b]) });
    tape.record(makeEvent("a"));
    expect(a.entries.length).toBe(1);
    expect(b.entries.length).toBe(1);
  });

  it("backend failures do not block the tape", () => {
    const flaky = {
      append() {
        throw new Error("disk full");
      },
    };
    const tape = new SessionTape({ backend: flaky });
    expect(() => tape.record(makeEvent("a"))).not.toThrow();
    expect(tape.size).toBe(1);
  });
});
