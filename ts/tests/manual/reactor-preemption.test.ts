/**
 * Reactor preemption determinism (parity with Python 0.18 fix).
 *
 * Python's `_reactor.py` awaits the victim handler's clean teardown
 * (`await asyncio.gather(victim, return_exceptions=True)`) before
 * dispatching the preempting rule, and its runner only clears the
 * running slot when it still owns it. That makes preemption
 * deterministic regardless of timing.
 *
 * These tests pin the TS port to the same guarantees:
 *  1. A preemptive higher-priority rule cancels the victim and the
 *     preemptor runs to completion.
 *  2. The victim's deferred teardown must NOT clobber the slot owned by
 *     the freshly-installed preemptor (stale-finish guard), nor spuriously
 *     drain the queue / run a queued rule concurrently with the preemptor.
 *  3. The non-preemptive path still runs both rules (queue drains in
 *     priority order, one at a time).
 */

import { describe, expect, it } from "vitest";

import { Signal, Reactor } from "../../src/namespaces/reactor.js";
import { AgentToken } from "../../src/namespaces/harness/lifecycle.js";

const tick = (ms = 0): Promise<void> => new Promise((res) => setTimeout(res, ms));

describe("Reactor preemption determinism", () => {
  it("preemptor runs after the victim is cancelled (cooperative victim)", async () => {
    const s = new Signal("x", 0);
    const log: string[] = [];
    let preempted = false;
    const r = new Reactor({
      onPreempt: () => {
        preempted = true;
      },
      cursor: () => 7,
    });

    const victimTokens: AgentToken[] = [];
    // Victim fires only on `is(1)`; preemptor fires only on `is(2)`. This
    // keeps the two triggers disjoint so we drive a clean victim-then-
    // preemptor sequence.
    r.when(
      s.is(1),
      async (ctx) => {
        if (ctx.token) victimTokens.push(ctx.token);
        log.push("victim-start");
        // Cooperative victim: yields and bails out once cancelled.
        for (let i = 0; i < 20; i += 1) {
          await tick(5);
          if (ctx.token?.cancelled) {
            log.push("victim-cancelled");
            return;
          }
        }
        log.push("victim-end"); // should NOT happen — it gets cancelled
      },
      { agentName: "victim", priority: 100 },
    );
    r.when(
      s.is(2),
      async () => {
        log.push("preemptor-start");
        await tick(5);
        log.push("preemptor-end");
      },
      { agentName: "preemptor", priority: 5, preemptive: true },
    );

    r.start();
    s.set(1); // victim starts and runs its cooperative loop
    await tick(8); // let the victim get into its loop
    s.set(2); // preemptor preempts the running victim
    await tick(60);

    // Preemption actually happened.
    expect(preempted).toBe(true);
    // The victim was cancelled with the resume cursor and never falsely
    // completed.
    expect(victimTokens.length).toBe(1);
    expect(victimTokens[0]!.cancelled).toBe(true);
    expect(victimTokens[0]!.resumeCursor).toBe(7);
    expect(log).toContain("victim-cancelled");
    expect(log).not.toContain("victim-end");
    // The preemptor ran cleanly to completion.
    expect(log).toContain("preemptor-start");
    expect(log).toContain("preemptor-end");
  });

  it("stale victim teardown does not clobber the preemptor's slot or drain the queue", async () => {
    const s = new Signal("x", 0);
    const log: string[] = [];
    let resolveVictim!: () => void;
    const victimGate = new Promise<void>((res) => {
      resolveVictim = res;
    });

    const r = new Reactor({ cursor: () => 1 });

    // Victim: a long-running preemptive-eligible handler whose teardown
    // is gated so we can settle it AFTER the preemptor is installed.
    r.when(
      s.is(1),
      async () => {
        log.push("victim-start");
        await victimGate; // settles only when we choose
        log.push("victim-end");
      },
      { agentName: "victim", priority: 100 },
    );

    // Preemptor: a long-running handler whose own gate lets us hold it
    // open while we settle the stale victim, then assert the preemptor's
    // slot survived.
    let resolvePre!: () => void;
    const preGate = new Promise<void>((res) => {
      resolvePre = res;
    });
    r.when(
      s.is(2),
      async () => {
        log.push("pre-start");
        await preGate;
        log.push("pre-end");
      },
      { agentName: "preemptor", priority: 5, preemptive: true },
    );

    // A queued lower-priority rule that must NOT be dispatched by a stale
    // victim teardown while the preemptor is still running.
    r.when(
      s.is(3),
      async () => {
        log.push("queued-run");
      },
      { agentName: "queued", priority: 200 },
    );

    r.start();

    s.set(1); // victim starts, awaits gate
    await tick(0);
    expect(log).toEqual(["victim-start"]);

    s.set(2); // preemptor preempts the (gated) victim and installs immediately
    await tick(0);
    // Cooperative cancellation: the preemptor does NOT block on the victim's
    // teardown, so it starts right away. The victim is still suspended on its
    // gate; its eventual `_finish` must not own the slot anymore.
    expect(log).toEqual(["victim-start", "pre-start"]);

    // Queue a lower-priority rule while the preemptor runs.
    s.set(3);
    await tick(0);
    // It must be queued, not run, because the preemptor is still running.
    expect(log).toEqual(["victim-start", "pre-start"]);

    // Now settle the STALE victim teardown. With the fix, the victim's
    // deferred `_finish` must NOT fire (it no longer owns the slot), so it
    // must NOT clear `_current` nor drain the "queued" rule.
    resolveVictim();
    await tick(5);
    expect(log).toEqual(["victim-start", "pre-start", "victim-end"]);
    // The queued rule must still be waiting — only the preemptor owns the slot.

    // Finish the preemptor. Its `_finish` owns the slot and drains the queue.
    resolvePre();
    await tick(5);
    expect(log).toContain("pre-end");
    expect(log).toContain("queued-run");
    // queued-run happens exactly once, after pre-end.
    expect(log.filter((l) => l === "queued-run").length).toBe(1);
    expect(log.indexOf("queued-run")).toBeGreaterThan(log.indexOf("pre-end"));
  });

  it("non-preemptive path runs both rules in priority order, one at a time", async () => {
    const s = new Signal("x", 0);
    const log: string[] = [];
    const r = new Reactor();

    r.when(
      s.changed,
      async () => {
        log.push("a-start");
        await tick(10);
        log.push("a-end");
      },
      { agentName: "a", priority: 50 },
    );
    r.when(
      s.changed,
      async () => {
        log.push("b-start");
        await tick(10);
        log.push("b-end");
      },
      { agentName: "b", priority: 100 },
    );

    r.start();
    s.set(1);
    await tick(60);

    // Higher priority (a=50) runs first to completion, then b. No overlap.
    expect(log).toEqual(["a-start", "a-end", "b-start", "b-end"]);
  });
});
