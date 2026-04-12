/**
 * Sandbox policies — pure data describing the file/network reach of tools.
 *
 * Mirrors `python/src/adk_fluent/_harness/_sandbox.py`. Sandbox policies
 * are passed to the workspace/processes/web tool factories so individual
 * tool calls can be vetted at runtime.
 */

import { resolveWithin } from "./types.js";

export interface SandboxPolicyOptions {
  /** Workspace root — every read/write must resolve under this directory. */
  workspace?: string | null;
  /** Allow `bash`/`process` style tools? */
  allowShell?: boolean;
  /** Allow network egress (web, fetch, MCP)? */
  allowNetwork?: boolean;
  /** Additional read-only paths outside the workspace. */
  readPaths?: Iterable<string>;
  /** Additional writable paths outside the workspace. */
  writePaths?: Iterable<string>;
  /** Hard cap on bash output capture (bytes). */
  maxOutputBytes?: number;
}

export class SandboxPolicy {
  readonly workspace: string | null;
  readonly allowShell: boolean;
  readonly allowNetwork: boolean;
  readonly readPaths: ReadonlySet<string>;
  readonly writePaths: ReadonlySet<string>;
  readonly maxOutputBytes: number;

  constructor(opts: SandboxPolicyOptions = {}) {
    this.workspace = opts.workspace ? normalizeAbs(opts.workspace) : null;
    this.allowShell = opts.allowShell ?? true;
    this.allowNetwork = opts.allowNetwork ?? true;
    this.readPaths = new Set([...(opts.readPaths ?? [])].map(normalizeAbs));
    this.writePaths = new Set([...(opts.writePaths ?? [])].map(normalizeAbs));
    this.maxOutputBytes = opts.maxOutputBytes ?? 100_000;
  }

  /** Throw if `target` cannot be read under this policy. */
  checkRead(target: string): string {
    return this.checkAccess(target, "read");
  }

  /** Throw if `target` cannot be written under this policy. */
  checkWrite(target: string): string {
    return this.checkAccess(target, "write");
  }

  private checkAccess(target: string, mode: "read" | "write"): string {
    const abs = normalizeAbs(target);
    if (this.workspace) {
      try {
        return resolveWithin(this.workspace, target);
      } catch {
        // fall through to extra paths below
      }
    }
    const extras = mode === "read" ? this.readPaths : this.writePaths;
    for (const p of extras) {
      if (abs === p || abs.startsWith(p + "/")) return abs;
    }
    if (!this.workspace && extras.size === 0) return abs;
    throw new Error(`Sandbox: ${mode} access denied for '${target}'`);
  }
}

function normalizeAbs(p: string): string {
  if (!p.startsWith("/")) {
    // Relative paths are resolved against the current working directory.
    p = `${process.cwd()}/${p}`;
  }
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
