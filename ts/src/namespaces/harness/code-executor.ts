/**
 * Polyglot code executor — run snippets of Python, Node, TypeScript, or Bash
 * inside a `SandboxPolicy`. The runner is the missing primitive that turns
 * the harness into a "Claude Code" style agent loop: rather than ask the
 * model to author whole files for every task, hand it a small `run_code`
 * tool and let it batch primitive operations in its native language.
 *
 * Design goals
 * ------------
 * - **Polyglot**: TS harness can launch `python3 -c …` or `node -e …`
 *   without the agent author having to know which interpreter is on $PATH.
 *   Auto-detect each language once on first use.
 * - **Sandboxed**: every spawn inherits the workspace cwd from
 *   `SandboxPolicy.workspace`, refuses to start when `allowShell === false`,
 *   and caps stdout/stderr at `sandbox.maxOutputBytes`.
 * - **Stateless**: no persistent REPL state between calls (this is *not*
 *   Jupyter). For session-scoped state the agent should write to a file.
 *   Stateless executors are easier to reason about and trivial to
 *   parallelize across forks.
 * - **Tool-shaped**: `executor.tools()` returns one LLM-callable
 *   `run_code({ language, source })` tool plus a thin `which_languages()`
 *   capability probe so the model can branch on what's installed.
 *
 * Why this is the right shape
 * ---------------------------
 * Claude Code conflates "shell" and "code execution" inside its single
 * `BashTool`. That works for an interactive engineer running mostly bash,
 * but it forces every Python snippet through `python3 -c "$(cat <<EOF …`
 * heredoc gymnastics. Splitting code execution into its own tool means:
 *
 * 1. The model can pass *raw* source — no shell-escaping Easter eggs.
 * 2. The model gets per-language hints (Python sees a `repr()`-friendly
 *    error trace, Node sees a `console.error` stack).
 * 3. The harness author can swap interpreters (e.g. `uv run python` vs
 *    `python3`, `bun` vs `node`) by pointing at a different binary in
 *    `CodeExecutorOptions.interpreters`.
 *
 * Pair this with `H.codingAgent(...)` for the full reduce-ceremony preset.
 */

import { spawn, type SpawnOptionsWithoutStdio } from "node:child_process";
import { existsSync, mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { type SandboxPolicy } from "./sandbox.js";
import { asTool, type HarnessTool } from "./types.js";

export type CodeLanguage = "python" | "node" | "typescript" | "bash" | "shell";

export interface CodeExecutorOptions {
  /**
   * Override the binary used for each language. Useful when the host has
   * multiple Python versions, or when the user prefers `bun` to `node`.
   *
   * Each entry can be a single binary name (`"python3.12"`) or a full
   * argv prefix (`["uv", "run", "python"]`).
   */
  interpreters?: Partial<Record<CodeLanguage, string | string[]>>;
  /** Default per-call wall clock in milliseconds. */
  defaultTimeoutMs?: number;
  /** Languages that should NOT be exposed even if their interpreter exists. */
  disable?: CodeLanguage[];
  /** Optional streaming sink for live stdout. */
  onOutput?: (chunk: string) => void;
}

export interface CodeRunResult {
  language: CodeLanguage;
  stdout: string;
  stderr: string;
  exitCode: number;
  truncated: boolean;
  durationMs: number;
}

const DEFAULT_INTERPRETERS: Record<CodeLanguage, string[]> = {
  python: ["python3"],
  node: ["node"],
  // typescript is intentionally distinct from `node`: tsx is the
  // standard "run a .ts file" runner. Falls back to `npx -y tsx` so the
  // common case works without a global install.
  typescript: ["npx", "-y", "tsx"],
  bash: ["bash"],
  shell: ["bash"],
};

/**
 * Polyglot code runner. Holds a `SandboxPolicy` reference and an
 * interpreter table; calling `.run(...)` shells out to the right binary.
 */
export class CodeExecutor {
  readonly sandbox: SandboxPolicy;
  readonly defaultTimeoutMs: number;
  private readonly interpreters: Record<CodeLanguage, string[]>;
  private readonly disabled: Set<CodeLanguage>;
  private readonly onOutput?: (chunk: string) => void;
  private detectedCache?: Record<CodeLanguage, boolean>;

  constructor(sandbox: SandboxPolicy, opts: CodeExecutorOptions = {}) {
    this.sandbox = sandbox;
    this.defaultTimeoutMs = opts.defaultTimeoutMs ?? 60_000;
    this.disabled = new Set(opts.disable ?? []);
    this.onOutput = opts.onOutput;
    const merged: Record<CodeLanguage, string[]> = { ...DEFAULT_INTERPRETERS };
    for (const [lang, bin] of Object.entries(opts.interpreters ?? {})) {
      if (bin == null) continue;
      merged[lang as CodeLanguage] = Array.isArray(bin) ? bin : [bin];
    }
    this.interpreters = merged;
  }

  /** Run `source` under the chosen language; returns captured streams. */
  async run(
    language: CodeLanguage,
    source: string,
    opts: { timeoutMs?: number; stdin?: string } = {},
  ): Promise<CodeRunResult> {
    if (!this.sandbox.allowShell) {
      throw new Error(`CodeExecutor: sandbox forbids shell — cannot run ${language}`);
    }
    if (this.disabled.has(language)) {
      throw new Error(`CodeExecutor: language '${language}' is disabled`);
    }
    const argv = this.interpreters[language];
    if (!argv) throw new Error(`CodeExecutor: unknown language '${language}'`);

    const cwd = this.sandbox.workspace ?? process.cwd();
    const timeoutMs = opts.timeoutMs ?? this.defaultTimeoutMs;
    const started = Date.now();

    // For bash/shell: pass via -c. For node: pass via -e. For python: pass
    // via -c. For typescript: write to a tmp file because tsx wants a path.
    const { command, args, cleanup } = await this.materialize(language, argv, source);

    return await new Promise<CodeRunResult>((resolve) => {
      const spawnOpts: SpawnOptionsWithoutStdio = { cwd, env: process.env };
      const child = spawn(command, args, spawnOpts);
      let stdout = "";
      let stderr = "";
      let truncated = false;

      const timer = setTimeout(() => {
        child.kill("SIGKILL");
        stderr += `\n[killed after ${timeoutMs}ms]`;
      }, timeoutMs);

      const cap = this.sandbox.maxOutputBytes;
      child.stdout.on("data", (chunk: Buffer) => {
        const s = chunk.toString("utf8");
        this.onOutput?.(s);
        if (stdout.length + s.length > cap) {
          stdout += s.slice(0, Math.max(0, cap - stdout.length));
          truncated = true;
        } else {
          stdout += s;
        }
      });
      child.stderr.on("data", (chunk: Buffer) => {
        const s = chunk.toString("utf8");
        if (stderr.length + s.length > cap) {
          stderr += s.slice(0, Math.max(0, cap - stderr.length));
          truncated = true;
        } else {
          stderr += s;
        }
      });

      if (opts.stdin != null) {
        child.stdin.write(opts.stdin);
        child.stdin.end();
      }

      const finish = (exitCode: number) => {
        clearTimeout(timer);
        cleanup?.();
        resolve({
          language,
          stdout,
          stderr,
          exitCode,
          truncated,
          durationMs: Date.now() - started,
        });
      };
      child.on("close", (code) => finish(code ?? 0));
      child.on("error", (err) => {
        stderr += (err as Error).message;
        finish(1);
      });
    });
  }

  /** Probe interpreters once and cache. Used by `which_languages` tool. */
  async detect(): Promise<Record<CodeLanguage, boolean>> {
    if (this.detectedCache) return this.detectedCache;
    const result = {} as Record<CodeLanguage, boolean>;
    for (const lang of Object.keys(this.interpreters) as CodeLanguage[]) {
      if (this.disabled.has(lang)) {
        result[lang] = false;
        continue;
      }
      result[lang] = await probeBinary(this.interpreters[lang][0]);
    }
    this.detectedCache = result;
    return result;
  }

  /** Build LLM-callable tools that wrap this executor. */
  tools(): HarnessTool[] {
    return [
      asTool(
        "run_code",
        async (args: { language: CodeLanguage; source: string; timeoutMs?: number }) => {
          const r = await this.run(args.language, args.source, { timeoutMs: args.timeoutMs });
          return {
            stdout: r.stdout,
            stderr: r.stderr,
            exitCode: r.exitCode,
            truncated: r.truncated,
            durationMs: r.durationMs,
          };
        },
      ),
      asTool("which_languages", async () => {
        return await this.detect();
      }),
    ];
  }

  // ─── interpreter argv assembly ──────────────────────────────────────────

  private async materialize(
    language: CodeLanguage,
    argv: string[],
    source: string,
  ): Promise<{ command: string; args: string[]; cleanup?: () => void }> {
    const [command, ...prefix] = argv;
    if (language === "python") {
      return { command, args: [...prefix, "-c", source] };
    }
    if (language === "node") {
      return { command, args: [...prefix, "-e", source] };
    }
    if (language === "bash" || language === "shell") {
      return { command, args: [...prefix, "-c", source] };
    }
    if (language === "typescript") {
      // tsx wants a file path. Write to a tmp file under the OS tmpdir.
      const dir = mkdtempSync(join(tmpdir(), "harness-tsx-"));
      const file = join(dir, "snippet.ts");
      writeFileSync(file, source, "utf8");
      return {
        command,
        args: [...prefix, file],
        cleanup: () => {
          try {
            // Best-effort cleanup; ignore errors.
            if (existsSync(file)) {
              // Lazy-import to keep startup cheap.
              import("node:fs").then((fs) => {
                try {
                  fs.unlinkSync(file);
                  fs.rmdirSync(dir);
                } catch {
                  /* ignore */
                }
              });
            }
          } catch {
            /* ignore */
          }
        },
      };
    }
    throw new Error(`CodeExecutor: unsupported language '${language}'`);
  }
}

// ─── helpers ───────────────────────────────────────────────────────────────

function probeBinary(bin: string): Promise<boolean> {
  return new Promise((resolve) => {
    const child = spawn(bin, ["--version"], { stdio: "ignore" });
    child.on("close", (code) => resolve(code === 0));
    child.on("error", () => resolve(false));
  });
}
