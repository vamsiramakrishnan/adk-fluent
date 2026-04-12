/**
 * Git checkpointer + git LLM tools.
 *
 * Mirrors `_harness/_git.py` and `_harness/_git_tools.py`. Both delegate
 * to the system `git` binary via `child_process.execFileSync`.
 */

import { execFileSync } from "node:child_process";
import { asTool, type HarnessTool } from "./types.js";

function git(workspace: string, args: string[]): string {
  try {
    return execFileSync("git", args, {
      cwd: workspace,
      encoding: "utf8",
      maxBuffer: 4 * 1024 * 1024,
    });
  } catch (err) {
    const e = err as { stderr?: Buffer | string; message?: string };
    const stderr = e.stderr
      ? Buffer.isBuffer(e.stderr)
        ? e.stderr.toString("utf8")
        : e.stderr
      : "";
    throw new Error(`git ${args.join(" ")}: ${stderr || e.message || "failed"}`);
  }
}

/**
 * Lightweight git "checkpointer". Stash-creates a labeled commit on a
 * scratch ref so the agent can roll back without polluting the working
 * branch history.
 */
export class GitCheckpointer {
  readonly workspace: string;

  constructor(workspace: string) {
    this.workspace = workspace;
  }

  /** Create a labeled checkpoint. Returns the commit SHA. */
  create(label: string): string {
    git(this.workspace, ["add", "-A"]);
    try {
      git(this.workspace, ["commit", "--allow-empty", "-m", `[checkpoint] ${label}`]);
    } catch {
      /* nothing to commit — fall through to rev-parse */
    }
    return git(this.workspace, ["rev-parse", "HEAD"]).trim();
  }

  /** Restore the working tree to a previously-created checkpoint. */
  restore(sha: string): void {
    git(this.workspace, ["reset", "--hard", sha]);
  }

  /** Show one-line log entries for recent checkpoints. */
  list(limit = 10): string[] {
    const out = git(this.workspace, ["log", `-${limit}`, "--oneline", "--grep=^\\[checkpoint\\]"]);
    return out.split("\n").filter(Boolean);
  }
}

export function gitTools(workspace: string, opts: { allowShell?: boolean } = {}): HarnessTool[] {
  const tools: HarnessTool[] = [];

  tools.push(asTool("git_status", async () => ({ output: git(workspace, ["status", "--short"]) })));
  tools.push(
    asTool("git_diff", async (args: { path?: string; staged?: boolean }) => {
      const argv = ["diff"];
      if (args?.staged) argv.push("--staged");
      if (args?.path) argv.push("--", args.path);
      return { output: git(workspace, argv) };
    }),
  );
  tools.push(
    asTool("git_log", async (args: { limit?: number }) => {
      return { output: git(workspace, ["log", `-${args?.limit ?? 10}`, "--oneline"]) };
    }),
  );
  tools.push(
    asTool("git_branch", async () => ({
      output: git(workspace, ["branch", "--show-current"]).trim(),
    })),
  );

  if (opts.allowShell ?? true) {
    tools.push(
      asTool("git_commit", async (args: { message: string }) => {
        git(workspace, ["add", "-A"]);
        return { output: git(workspace, ["commit", "-m", args.message]) };
      }),
    );
  }

  return tools;
}
