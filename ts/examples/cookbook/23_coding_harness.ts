/**
 * 23 — Coding Harness (H namespace)
 *
 * `H.codingAgent(workspace)` returns a fully-wired bundle for building a
 * Claude-Code-style coding agent: workspace tools, web fetch, processes,
 * git, polyglot code executor, todos/plan-mode, sandbox + permissions.
 *
 * Drop the bundle's `.tools` straight into an Agent and you have a coding
 * agent. Every primitive is exposed individually so you can swap or
 * augment any piece.
 */
import assert from "node:assert/strict";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { Agent, H } from "../../src/index.js";

// Use a tmpdir as the workspace — H.codingAgent eagerly creates the
// artifact store directory and reads/writes the project-memory file.
const workspace = mkdtempSync(join(tmpdir(), "adk-fluent-cookbook-"));

const harness = H.codingAgent(workspace, {
  allowMutations: true,
  allowNetwork: false, // research-mode-ish: shell yes, network no
  enableGit: false,
});

// Bundle exposes the workspace and every primitive for swap-out.
assert.equal(harness.workspace, workspace);
assert.ok(Array.isArray(harness.tools));
assert.ok(harness.tools.length > 0);
assert.ok(harness.sandbox);
assert.ok(harness.permissions);
assert.ok(harness.executor);
assert.ok(harness.todos);
assert.ok(harness.planMode);

// Wire the bundle into an Agent — one line.
const coder = new Agent("coder", "gemini-2.5-pro")
  .instruct("You are a senior engineer. Use the provided tools to ship.")
  .tools(harness.tools)
  .build() as Record<string, unknown>;

assert.equal(coder._type, "LlmAgent");
// `.tools(arr)` appends the array as a single list entry; the inner array
// holds the harness tools. Either spread per-call or unwrap when asserting.
const builtTools = coder.tools as unknown[];
assert.equal(builtTools.length, 1);
assert.equal((builtTools[0] as unknown[]).length, harness.tools.length);

export { harness, coder };
