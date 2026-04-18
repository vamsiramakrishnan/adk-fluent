/**
 * Stream replay — resume a stream from a tape cursor.
 *
 * Mirrors `python/src/adk_fluent/_helpers.py::stream_from_cursor`. The
 * helper drains buffered events whose `seq >= fromSeq` first, then
 * transitions into a live tail that yields every subsequent event of
 * the requested kind. The canonical use case is resuming a streaming
 * text render after a disconnect without losing or duplicating chunks.
 */

import type { EventRecord, HarnessEventKind, SessionTape } from "./events.js";

export interface StreamFromCursorOptions {
  /** Only yield events with this kind. Default: `"text"`. Pass `null` for all. */
  kind?: HarnessEventKind | null;
  /** Stop when this signal aborts. */
  signal?: AbortSignal;
}

/**
 * Replay a tape starting at `fromSeq`, then follow live writes.
 *
 * The iterator is open-ended unless `signal` aborts — callers are
 * responsible for their own termination condition.
 */
export async function* streamFromCursor(
  tape: SessionTape,
  fromSeq: number,
  opts: StreamFromCursorOptions = {},
): AsyncIterable<EventRecord> {
  const kind = opts.kind === undefined ? "text" : opts.kind;
  let drainedSeq = fromSeq;
  for (const entry of tape.since(fromSeq)) {
    if (kind !== null && entry.kind !== kind) {
      drainedSeq = (entry.seq ?? drainedSeq) + 1;
      continue;
    }
    yield entry;
    drainedSeq = (entry.seq ?? drainedSeq) + 1;
  }
  for await (const entry of tape.tail(drainedSeq, { signal: opts.signal })) {
    if (kind !== null && entry.kind !== kind) continue;
    yield entry;
  }
}
