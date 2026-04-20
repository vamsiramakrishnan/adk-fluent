/**
 * 81 — R + Agent.on() — declarative reactors, zero ceremony.
 *
 * The 0.17.0 reactor refresh makes signals and rules a first-class part
 * of the fluent builder surface. Before, wiring a reactor required
 * hand-building every object in sequence:
 *
 *     const bus  = new EventBus();
 *     const temp = new Signal("temp", 72).attach(bus);
 *     const r    = new Reactor();
 *     r.when(temp.rising.where((v) => (v as number) > 90),
 *            myHandler,
 *            { priority: 10 });
 *     r.start();
 *
 * Now:
 *
 *     const temp = R.signal("temp", 72);
 *
 *     const cooler = new Agent("cooler", "gemini-2.5-flash")
 *       .instruct("Plan a cool-down.")
 *       .on(R.rising("temp").where((v) => (v as number) > 90),
 *           handler,
 *           { priority: 10 });
 *
 *     const reactor = R.compile([cooler], { bus });
 *     reactor.start();
 *
 * Ported from Python cookbook `81_reactor_native.py`.
 */
import assert from "node:assert/strict";
import {
  Agent,
  FanOut,
  Pipeline,
  R,
  ReactorPlugin,
  SignalPredicate,
} from "../../src/index.js";
import { EventBus } from "../../src/namespaces/harness/events.js";

// ───────────────────────────────────────────────────────────────────────────
// 1. R.signal is name-addressed — get-or-create, same name → same instance.
// ───────────────────────────────────────────────────────────────────────────
R.clear();
{
  const a = R.signal("temperature", 72);
  const b = R.signal("temperature");
  assert.equal(a, b);
  assert.equal(R.get<number>("temperature").get(), 72);
}

// ───────────────────────────────────────────────────────────────────────────
// 2. Predicates are name-addressed — no Signal object juggling.
// ───────────────────────────────────────────────────────────────────────────
R.clear();
{
  R.signal("temperature", 0);
  const pred = R.rising("temperature").where((v) => (v as number) > 90);
  assert.ok(pred instanceof SignalPredicate);
  assert.equal(pred.deps[0]!.name, "temperature");
}

// ───────────────────────────────────────────────────────────────────────────
// 3. `.on(predicate, handler)` stores a declarative rule on the builder.
// ───────────────────────────────────────────────────────────────────────────
R.clear();
{
  R.signal("temp", 0);
  const agent = new Agent("cooler").on(R.rising("temp"), () => {}, {
    priority: 10,
  });
  const spec = agent._reactor_rules[0]!;
  assert.equal(spec.predicate.deps[0]!.name, "temp");
  assert.equal(spec.priority, 10);
}

// ───────────────────────────────────────────────────────────────────────────
// 4. R.compile walks composite builders (Pipeline / FanOut).
// ───────────────────────────────────────────────────────────────────────────
R.clear();
{
  R.signal("a", 0);
  R.signal("b", 0);

  const pipeline = new Pipeline("flow").step(
    new Agent("x").on(R.changed("a"), () => {}),
  );
  const fanout = new FanOut("parallel")
    .branch(new Agent("y").on(R.changed("a"), () => {}))
    .branch(new Agent("z").on(R.changed("b"), () => {}));

  const reactorP = R.compile([pipeline]);
  const reactorF = R.compile([fanout]);

  assert.equal(reactorP.getRules().length, 1);
  assert.equal(reactorF.getRules().length, 2);
}

// ───────────────────────────────────────────────────────────────────────────
// 5. End-to-end: R.signal → .on(R.rising()) → R.compile → reactor fires.
// ───────────────────────────────────────────────────────────────────────────
R.clear();
{
  const bus = new EventBus({ maxBuffer: 100 });
  R.attach(bus);
  const temp = R.signal("temp", 72);

  const fires: Array<[unknown, unknown]> = [];
  const handler = async (ctx: { current: unknown; previous: unknown }) => {
    fires.push([ctx.current, ctx.previous]);
  };

  const cooler = new Agent("cooler", "gemini-2.5-flash")
    .instruct("Cool the building.")
    .on(R.rising("temp").where((v) => (v as number) > 90), handler, {
      priority: 10,
    });

  const reactor = R.compile([cooler], { bus });
  reactor.start();

  temp.set(80); // rising but below 90 — no fire
  temp.set(95); // rising above 90 — fires
  temp.set(92); // falling — no fire

  await new Promise((resolve) => setTimeout(resolve, 20));
  reactor.stop();

  assert.deepEqual(fires, [[95, 80]]);
}

// ───────────────────────────────────────────────────────────────────────────
// 6. ReactorPlugin owns the reactor's lifecycle.
// ───────────────────────────────────────────────────────────────────────────
R.clear();
{
  const bus = new EventBus({ maxBuffer: 100 });
  R.attach(bus);
  const sig = R.signal("ping", false);

  let fired = false;
  const agent = new Agent("listener").on(R.changed("ping"), async () => {
    fired = true;
  });

  const reactor = R.compile([agent], { bus });
  const plugin = new ReactorPlugin(reactor);

  await plugin.onSessionStart();
  sig.set(true);
  await new Promise((resolve) => setTimeout(resolve, 20));
  await plugin.onSessionEnd();
  assert.equal(fired, true);
}

// ───────────────────────────────────────────────────────────────────────────
// 7. debounce/throttle are immutable — fresh predicates returned.
// ───────────────────────────────────────────────────────────────────────────
R.clear();
{
  R.signal("temp", 0);
  const base = R.changed("temp");
  const debounced = base.debounce(50);
  assert.notEqual(debounced, base);
  assert.equal(base._debounceMsValue, 0);
  assert.equal(debounced._debounceMsValue, 50);
}

R.clear();
