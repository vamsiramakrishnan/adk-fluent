/**
 * Phase D: streamFromCursor — replay tape then tail live.
 *
 * Mirrors python/tests/manual/test_stream_from_cursor.py.
 */

import { describe, expect, it } from "vitest";

import { SessionTape, type HarnessEvent } from "../../src/namespaces/harness/events.js";
import { streamFromCursor } from "../../src/namespaces/harness/stream-replay.js";

function makeText(text: string): HarnessEvent {
  return { kind: "text", text, timestamp: Date.now() };
}

describe("streamFromCursor", () => {
  it("drains history then follows live writes", async () => {
    const tape = new SessionTape();
    tape.record(makeText("a"));
    tape.record(makeText("b"));

    const ctrl = new AbortController();
    const collected: string[] = [];
    const done = (async () => {
      for await (const entry of streamFromCursor(tape, 0, { signal: ctrl.signal })) {
        collected.push((entry as { text: string }).text);
        if (collected.length === 4) ctrl.abort();
      }
    })();
    // Live writes after iterator starts.
    await new Promise((r) => setTimeout(r, 5));
    tape.record(makeText("c"));
    tape.record(makeText("d"));
    await done;

    expect(collected).toEqual(["a", "b", "c", "d"]);
  });

  it("filters by kind by default (text only)", async () => {
    const tape = new SessionTape();
    tape.record({ kind: "tool_call_start", toolName: "bash", timestamp: 0 });
    tape.record(makeText("hello"));
    tape.record({ kind: "tool_call_end", toolName: "bash", timestamp: 0 });

    const ctrl = new AbortController();
    const collected: string[] = [];
    const done = (async () => {
      for await (const entry of streamFromCursor(tape, 0, { signal: ctrl.signal })) {
        collected.push((entry as { text: string }).text);
        ctrl.abort();
      }
    })();
    await done;
    expect(collected).toEqual(["hello"]);
  });

  it("respects fromSeq to skip earlier events", async () => {
    const tape = new SessionTape();
    tape.record(makeText("a"));
    tape.record(makeText("b"));
    tape.record(makeText("c"));

    const ctrl = new AbortController();
    const collected: string[] = [];
    const done = (async () => {
      for await (const entry of streamFromCursor(tape, 2, { signal: ctrl.signal })) {
        collected.push((entry as { text: string }).text);
        if (collected.length === 1) ctrl.abort();
      }
    })();
    await done;
    expect(collected).toEqual(["c"]);
  });

  it("kind=null yields every entry", async () => {
    const tape = new SessionTape();
    tape.record({ kind: "tool_call_start", toolName: "bash", timestamp: 0 });
    tape.record(makeText("x"));
    const ctrl = new AbortController();
    const seen: string[] = [];
    const done = (async () => {
      for await (const entry of streamFromCursor(tape, 0, { kind: null, signal: ctrl.signal })) {
        seen.push(entry.kind);
        if (seen.length === 2) ctrl.abort();
      }
    })();
    await done;
    expect(seen).toEqual(["tool_call_start", "text"]);
  });
});
