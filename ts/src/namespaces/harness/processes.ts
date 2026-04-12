/**
 * Background process management — start_process, check_process, stop_process.
 *
 * Mirrors `_harness/_processes.py`. Long-running commands (dev servers,
 * builds) get a stable id so the LLM can poll status and read output.
 */

import { spawn, type ChildProcess } from "node:child_process";
import { type SandboxPolicy } from "./sandbox.js";
import { asTool, type HarnessTool } from "./types.js";

interface ProcRecord {
  id: string;
  command: string;
  child: ChildProcess;
  stdout: string;
  stderr: string;
  status: "running" | "exited" | "killed";
  exitCode: number | null;
  startedAt: number;
}

export function processTools(sandbox: SandboxPolicy): HarnessTool[] {
  const procs = new Map<string, ProcRecord>();
  let nextId = 1;
  const cwd = sandbox.workspace ?? process.cwd();
  const maxBytes = sandbox.maxOutputBytes;

  const tools: HarnessTool[] = [];

  tools.push(
    asTool("start_process", async (args: { command: string; name?: string }) => {
      if (!sandbox.allowShell) throw new Error("Shell disabled by sandbox");
      const id = args.name ?? `proc-${nextId++}`;
      const child = spawn("bash", ["-c", args.command], { cwd });
      const rec: ProcRecord = {
        id,
        command: args.command,
        child,
        stdout: "",
        stderr: "",
        status: "running",
        exitCode: null,
        startedAt: Date.now(),
      };
      child.stdout?.on("data", (chunk: Buffer) => {
        rec.stdout += chunk.toString("utf8");
        if (rec.stdout.length > maxBytes) rec.stdout = rec.stdout.slice(-maxBytes);
      });
      child.stderr?.on("data", (chunk: Buffer) => {
        rec.stderr += chunk.toString("utf8");
        if (rec.stderr.length > maxBytes) rec.stderr = rec.stderr.slice(-maxBytes);
      });
      child.on("close", (code, signal) => {
        rec.status = signal ? "killed" : "exited";
        rec.exitCode = code;
      });
      procs.set(id, rec);
      return { id, status: rec.status };
    }),
  );

  tools.push(
    asTool("check_process", async (args: { id: string }) => {
      const rec = procs.get(args.id);
      if (!rec) return { error: `No process '${args.id}'` };
      return {
        id: rec.id,
        status: rec.status,
        exitCode: rec.exitCode,
        stdout: rec.stdout,
        stderr: rec.stderr,
        elapsedMs: Date.now() - rec.startedAt,
      };
    }),
  );

  tools.push(
    asTool("stop_process", async (args: { id: string }) => {
      const rec = procs.get(args.id);
      if (!rec) return { error: `No process '${args.id}'` };
      if (rec.status === "running") {
        rec.child.kill("SIGTERM");
        rec.status = "killed";
      }
      return { id: rec.id, status: rec.status };
    }),
  );

  tools.push(
    asTool("list_processes", async () => {
      return [...procs.values()].map((r) => ({ id: r.id, status: r.status, command: r.command }));
    }),
  );

  return tools;
}
