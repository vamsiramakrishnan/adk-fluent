/**
 * Workspace tool factory — sandboxed read/write/glob/grep/ls/edit/bash.
 *
 * Mirrors `_harness/_tools.py` but uses Node's built-in fs and child_process
 * APIs instead of Python's pathlib + subprocess.
 *
 * All path arguments are resolved through `SandboxPolicy.checkRead/Write`,
 * which throws on path escape attempts. Bash output is hard-capped at
 * `sandbox.maxOutputBytes`.
 */

import { spawn } from "node:child_process";
import { existsSync, mkdirSync, readFileSync, readdirSync, statSync, writeFileSync } from "node:fs";
import { dirname, join, relative } from "node:path";
import { type SandboxPolicy } from "./sandbox.js";
import { asTool, type HarnessTool } from "./types.js";

export interface WorkspaceOptions {
  readOnly?: boolean;
  streaming?: boolean;
  diffMode?: boolean;
  multimodal?: boolean;
  onOutput?: (chunk: string) => void;
}

/**
 * Build the standard workspace tool kit.
 *
 * Default tools (7): read_file, write_file, glob, grep, ls, edit_file, bash.
 * `readOnly: true` drops write_file and edit_file.
 */
export function workspaceTools(sandbox: SandboxPolicy, opts: WorkspaceOptions = {}): HarnessTool[] {
  const root = sandbox.workspace ?? process.cwd();
  const tools: HarnessTool[] = [];

  tools.push(
    asTool("read_file", async (args: { path: string; offset?: number; limit?: number }) => {
      const abs = sandbox.checkRead(join(root, args.path));
      const text = readFileSync(abs, "utf8");
      if (args.offset == null && args.limit == null) return { content: text };
      const lines = text.split("\n");
      const start = args.offset ?? 0;
      const end = args.limit != null ? start + args.limit : lines.length;
      return { content: lines.slice(start, end).join("\n") };
    }),
  );

  tools.push(
    asTool("ls", async (args: { path?: string }) => {
      const target = args.path ? join(root, args.path) : root;
      const abs = sandbox.checkRead(target);
      const entries = readdirSync(abs).map((name) => {
        const st = statSync(join(abs, name));
        return { name, isDir: st.isDirectory(), size: st.size };
      });
      return { entries };
    }),
  );

  tools.push(
    asTool("glob", async (args: { pattern: string; path?: string }) => {
      const start = args.path ? sandbox.checkRead(join(root, args.path)) : root;
      const matches: string[] = [];
      const re = globToRegExp(args.pattern);
      walk(start, (file) => {
        const rel = relative(root, file);
        if (re.test(rel)) matches.push(rel);
      });
      return { matches };
    }),
  );

  tools.push(
    asTool("grep", async (args: { pattern: string; path?: string; flags?: string }) => {
      const start = args.path ? sandbox.checkRead(join(root, args.path)) : root;
      const re = new RegExp(args.pattern, args.flags ?? "");
      const hits: Array<{ file: string; line: number; text: string }> = [];
      walk(start, (file) => {
        try {
          const text = readFileSync(file, "utf8");
          const lines = text.split("\n");
          for (let i = 0; i < lines.length; i++) {
            if (re.test(lines[i])) {
              hits.push({ file: relative(root, file), line: i + 1, text: lines[i] });
            }
          }
        } catch {
          /* binary or unreadable file */
        }
      });
      return { hits };
    }),
  );

  if (!opts.readOnly) {
    tools.push(
      asTool("write_file", async (args: { path: string; content: string }) => {
        const abs = sandbox.checkWrite(join(root, args.path));
        mkdirSync(dirname(abs), { recursive: true });
        writeFileSync(abs, args.content, "utf8");
        return { ok: true, bytes: Buffer.byteLength(args.content, "utf8") };
      }),
    );

    tools.push(
      asTool(
        "edit_file",
        async (args: {
          path: string;
          oldString: string;
          newString: string;
          replaceAll?: boolean;
        }) => {
          const abs = sandbox.checkWrite(join(root, args.path));
          if (!existsSync(abs)) throw new Error(`File not found: ${args.path}`);
          const original = readFileSync(abs, "utf8");
          let updated: string;
          if (args.replaceAll) {
            updated = original.split(args.oldString).join(args.newString);
          } else {
            const idx = original.indexOf(args.oldString);
            if (idx === -1) throw new Error("oldString not found");
            if (original.indexOf(args.oldString, idx + 1) !== -1) {
              throw new Error("oldString is not unique — pass replaceAll: true");
            }
            updated =
              original.slice(0, idx) + args.newString + original.slice(idx + args.oldString.length);
          }
          writeFileSync(abs, updated, "utf8");
          return { ok: true };
        },
      ),
    );
  }

  if (sandbox.allowShell) {
    tools.push(
      asTool("bash", async (args: { command: string; timeoutMs?: number }) => {
        return await runBash(
          args.command,
          root,
          sandbox.maxOutputBytes,
          args.timeoutMs ?? 60_000,
          opts.onOutput,
        );
      }),
    );
  }

  return tools;
}

// ─── helpers ───────────────────────────────────────────────────────────────

function walk(root: string, visit: (file: string) => void): void {
  const stack: string[] = [root];
  for (;;) {
    const cur = stack.pop();
    if (cur === undefined) break;
    let st;
    try {
      st = statSync(cur);
    } catch {
      continue;
    }
    if (st.isDirectory()) {
      // Skip common noise directories.
      const base = cur.split("/").pop() ?? "";
      if (["node_modules", ".git", "dist", "__pycache__", ".venv"].includes(base)) continue;
      try {
        for (const entry of readdirSync(cur)) stack.push(join(cur, entry));
      } catch {
        /* unreadable directory */
      }
    } else if (st.isFile()) {
      visit(cur);
    }
  }
}

function globToRegExp(pattern: string): RegExp {
  const re =
    "^" +
    pattern
      .replace(/[.+^${}()|[\]\\]/g, "\\$&")
      .replace(/\*\*/g, "::DS::")
      .replace(/\*/g, "[^/]*")
      .replace(/::DS::/g, ".*")
      .replace(/\?/g, ".") +
    "$";
  return new RegExp(re);
}

interface BashResult {
  stdout: string;
  stderr: string;
  exitCode: number;
  truncated: boolean;
}

function runBash(
  command: string,
  cwd: string,
  maxBytes: number,
  timeoutMs: number,
  onOutput?: (chunk: string) => void,
): Promise<BashResult> {
  return new Promise((resolve) => {
    const child = spawn("bash", ["-c", command], { cwd });
    let stdout = "";
    let stderr = "";
    let truncated = false;

    const timer = setTimeout(() => {
      child.kill("SIGKILL");
      stderr += `\n[killed after ${timeoutMs}ms]`;
    }, timeoutMs);

    child.stdout.on("data", (chunk: Buffer) => {
      const s = chunk.toString("utf8");
      onOutput?.(s);
      if (stdout.length + s.length > maxBytes) {
        stdout += s.slice(0, Math.max(0, maxBytes - stdout.length));
        truncated = true;
      } else {
        stdout += s;
      }
    });
    child.stderr.on("data", (chunk: Buffer) => {
      const s = chunk.toString("utf8");
      if (stderr.length + s.length > maxBytes) {
        stderr += s.slice(0, Math.max(0, maxBytes - stderr.length));
        truncated = true;
      } else {
        stderr += s;
      }
    });
    child.on("close", (code) => {
      clearTimeout(timer);
      resolve({ stdout, stderr, exitCode: code ?? 0, truncated });
    });
    child.on("error", (err) => {
      clearTimeout(timer);
      resolve({ stdout, stderr: stderr + (err as Error).message, exitCode: 1, truncated });
    });
  });
}
