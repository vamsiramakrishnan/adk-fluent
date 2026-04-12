/**
 * Shared harness types — see `./H.ts` for the public namespace.
 */

import type { ToolFn } from "../../core/types.js";

/** A harness "tool" is just an async function with a `.toolName` brand. */
export type HarnessTool = ToolFn & { toolName: string };

/** Tag a function as a tool with a stable name. */
export function asTool(name: string, fn: ToolFn): HarnessTool {
  Object.defineProperty(fn, "name", { value: name, configurable: true });
  const tagged = fn as unknown as HarnessTool;
  tagged.toolName = name;
  return tagged;
}

/** Convert a frozen set / array / undefined into a `Set<string>`. */
export function toSet(input: Iterable<string> | undefined | null): Set<string> {
  return new Set(input ?? []);
}

/** Resolve a path relative to a workspace root, throwing on traversal. */
export function resolveWithin(workspace: string, target: string): string {
  // Use POSIX semantics; harness is not Windows-aware in v1.
  const path = target.startsWith("/") ? target : `${workspace}/${target}`;
  const normalized = normalizePath(path);
  const root = normalizePath(workspace);
  if (!normalized.startsWith(root + "/") && normalized !== root) {
    throw new Error(`Path escape: '${target}' resolves outside workspace '${workspace}'`);
  }
  return normalized;
}

function normalizePath(p: string): string {
  const parts: string[] = [];
  for (const seg of p.split("/")) {
    if (seg === "" || seg === ".") continue;
    if (seg === "..") {
      parts.pop();
      continue;
    }
    parts.push(seg);
  }
  return "/" + parts.join("/");
}
