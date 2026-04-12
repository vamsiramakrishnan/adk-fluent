/**
 * 13 — State Transforms (S namespace)
 *
 * The `S` namespace ships pure state→state functions for picking, dropping,
 * renaming, computing, and validating fields. They're applied via the
 * `STransform.apply()` method or composed with `.pipe()`.
 */
import assert from "node:assert/strict";
import { S } from "../../src/index.js";

const initial = { user: "alice", age: 30, internal: "secret", role: "admin" };

// pick — keep only the listed keys
const picked = S.pick("user", "role").apply(initial);
assert.deepEqual(picked, { user: "alice", role: "admin" });

// drop — remove the listed keys
const dropped = S.drop("internal").apply(initial);
assert.equal(dropped.internal, undefined);

// rename — `user` → `username`
const renamed = S.rename({ user: "username" }).apply(initial);
assert.equal(renamed.username, "alice");
assert.equal(renamed.user, undefined);

// transform — apply a function to one key
const upcased = S.transform("user", (v) => String(v).toUpperCase()).apply(initial);
assert.equal(upcased.user, "ALICE");

// compute — derive new fields from state
const enriched = S.compute({
  is_adult: (s) => Number(s.age) >= 18,
  display: (s) => `${s.user}<${s.role}>`,
}).apply(initial);
assert.equal(enriched.is_adult, true);
assert.equal(enriched.display, "alice<admin>");

// pipe — chain transforms
const piped = S.pick("user", "age", "role")
  .pipe(S.rename({ role: "permission" }))
  .apply(initial);
assert.deepEqual(piped, { user: "alice", age: 30, permission: "admin" });

export { picked, dropped, renamed, upcased, enriched, piped };
