/**
 * Persistent project memory — a markdown file that survives across sessions.
 *
 * Mirrors `_harness/_memory.py`. Composes with `C.fromState(...)` /
 * `Agent.reads(...)` to inject the loaded content into the agent's prompt.
 */

import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname } from "node:path";

export interface ProjectMemoryOptions {
  stateKey?: string;
  maxEntries?: number;
}

export class ProjectMemory {
  readonly path: string;
  readonly stateKey: string;
  readonly maxEntries: number;

  constructor(path: string, opts: ProjectMemoryOptions = {}) {
    this.path = path;
    this.stateKey = opts.stateKey ?? "project_memory";
    this.maxEntries = opts.maxEntries ?? 100;
  }

  /** Read the memory file (or empty string if missing). */
  load(): string {
    if (!existsSync(this.path)) return "";
    return readFileSync(this.path, "utf8");
  }

  /** Overwrite the memory file. */
  save(content: string): void {
    mkdirSync(dirname(this.path), { recursive: true });
    writeFileSync(this.path, content, "utf8");
  }

  /** Append a markdown bullet, trimming to `maxEntries`. */
  append(entry: string): void {
    const lines = this.load().split("\n").filter(Boolean);
    lines.push(`- ${entry}`);
    while (lines.length > this.maxEntries) lines.shift();
    this.save(lines.join("\n") + "\n");
  }

  /** Build a before-agent callback that injects memory into state. */
  loadCallback(): (state: Record<string, unknown>) => void {
    return (state) => {
      state[this.stateKey] = this.load();
    };
  }

  /** Build an after-agent callback that persists state[stateKey]. */
  saveCallback(): (state: Record<string, unknown>) => void {
    return (state) => {
      const value = state[this.stateKey];
      if (typeof value === "string") this.save(value);
    };
  }
}

/**
 * Multi-file memory hierarchy — load and merge files in priority order
 * (first = lowest priority, last = highest). Mirrors the CLAUDE.md
 * convention.
 */
export class MemoryHierarchy {
  readonly paths: readonly string[];
  readonly stateKey: string;

  constructor(paths: readonly string[], stateKey = "project_memory") {
    this.paths = paths;
    this.stateKey = stateKey;
  }

  load(): string {
    const chunks: string[] = [];
    for (const p of this.paths) {
      if (existsSync(p)) {
        chunks.push(`<!-- ${p} -->\n${readFileSync(p, "utf8")}`);
      }
    }
    return chunks.join("\n\n");
  }

  loadCallback(): (state: Record<string, unknown>) => void {
    return (state) => {
      state[this.stateKey] = this.load();
    };
  }
}
