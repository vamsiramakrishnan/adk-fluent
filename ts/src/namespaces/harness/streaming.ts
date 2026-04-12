/**
 * Streaming bash — async-iterator shell with real-time output chunks.
 *
 * The TypeScript port of `python/src/adk_fluent/_harness/_streaming.py`.
 *
 * Unlike the blocking process tools, `StreamingBash` yields output as it
 * arrives, which is essential for long-running commands (builds, tests,
 * installs) where the LLM or user wants progressive feedback.
 *
 * Usage:
 * ```ts
 * const streamer = new StreamingBash(sandbox);
 * for await (const chunk of streamer.run("npm test")) {
 *   process.stdout.write(chunk);
 * }
 * ```
 */

import { spawn } from "node:child_process";
import { type SandboxPolicy } from "./sandbox.js";

export interface StreamingBashRunOptions {
  /** Maximum execution time in seconds. Defaults to 120. */
  timeoutSec?: number;
  /** Optional callback fired for each output chunk before it is yielded. */
  onOutput?: (chunk: string) => void;
}

/**
 * Streaming shell executor.
 *
 * Spawns commands via `bash -c <command>` inside the sandbox workspace,
 * yielding stdout+stderr chunks as they arrive. Honors `sandbox.allowShell`,
 * `sandbox.workspace`, and `sandbox.maxOutputBytes` exactly like the
 * blocking `processTools()` flow.
 */
export class StreamingBash {
  constructor(public readonly sandbox: SandboxPolicy) {}

  /**
   * Execute a command and yield output chunks as they arrive.
   *
   * Output is decoded as UTF-8. Stderr is merged into stdout. The iterator
   * completes when the process exits, the timeout fires, or the cumulative
   * output exceeds `sandbox.maxOutputBytes`.
   */
  async *run(command: string, opts: StreamingBashRunOptions = {}): AsyncIterableIterator<string> {
    if (!this.sandbox.allowShell) {
      yield "Error: shell execution is disabled by sandbox policy.";
      return;
    }

    const timeoutSec = opts.timeoutSec ?? 120;
    const cwd = this.sandbox.workspace ?? process.cwd();
    const maxBytes = this.sandbox.maxOutputBytes;

    const child = spawn("bash", ["-c", command], { cwd });

    // Buffered chunk queue. The producer (stdout/stderr listeners and the
    // exit/error handlers) push items; the consumer (this generator) drains
    // them via the resolver-promise pattern below.
    type Item = { kind: "chunk"; value: string } | { kind: "end"; value?: string };
    const queue: Item[] = [];
    let resolveNext: (() => void) | null = null;
    const wake = () => {
      if (resolveNext) {
        const r = resolveNext;
        resolveNext = null;
        r();
      }
    };

    let totalBytes = 0;
    let killed = false;

    const handleData = (chunk: Buffer) => {
      if (killed) return;
      let text = chunk.toString("utf8");
      totalBytes += chunk.length;
      if (totalBytes > maxBytes) {
        text += `\n... (truncated to ${maxBytes} bytes)`;
        queue.push({ kind: "chunk", value: text });
        queue.push({ kind: "end" });
        killed = true;
        child.kill("SIGTERM");
        wake();
        return;
      }
      queue.push({ kind: "chunk", value: text });
      wake();
    };

    child.stdout?.on("data", handleData);
    child.stderr?.on("data", handleData);

    child.on("error", (err) => {
      queue.push({ kind: "end", value: `Error executing command: ${err.message}` });
      wake();
    });

    child.on("close", (code, signal) => {
      const trailing =
        signal && !killed
          ? `\nProcess terminated by ${signal}`
          : code != null && code !== 0
            ? `\nExit code: ${code}`
            : undefined;
      queue.push({ kind: "end", value: trailing });
      wake();
    });

    const timer = setTimeout(() => {
      if (!killed) {
        killed = true;
        child.kill("SIGKILL");
        queue.push({ kind: "end", value: `\nError: command timed out after ${timeoutSec}s` });
        wake();
      }
    }, timeoutSec * 1000);
    // Don't keep the event loop alive on the timeout alone.
    timer.unref?.();

    try {
      while (true) {
        if (queue.length === 0) {
          await new Promise<void>((resolve) => {
            resolveNext = resolve;
          });
        }
        const item = queue.shift();
        if (!item) continue;
        if (item.kind === "end") {
          if (item.value) {
            if (opts.onOutput) opts.onOutput(item.value);
            yield item.value;
          }
          return;
        }
        if (opts.onOutput) opts.onOutput(item.value);
        yield item.value;
      }
    } finally {
      clearTimeout(timer);
      if (!killed && child.exitCode == null) {
        try {
          child.kill("SIGTERM");
        } catch {
          // process already gone
        }
      }
    }
  }

  /**
   * Execute a command and return the full collected output as a string.
   *
   * Like `run()` but joins every chunk. If `onOutput` is supplied it still
   * fires for each chunk as it arrives, so callers can stream and collect
   * simultaneously.
   */
  async runCollected(command: string, opts: StreamingBashRunOptions = {}): Promise<string> {
    const parts: string[] = [];
    for await (const chunk of this.run(command, opts)) {
      parts.push(chunk);
    }
    return parts.join("");
  }
}
