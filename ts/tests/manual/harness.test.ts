/**
 * Smoke tests for the H namespace — sandbox, code executor, agent tools,
 * and the codingAgent preset. Hits real subprocesses for python/node/bash
 * so the tests are skipped on machines without those interpreters.
 */
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterAll, beforeAll, describe, expect, it } from "vitest";
import { H } from "../../src/namespaces/harness/H.js";
import { TodoStore, PlanMode } from "../../src/namespaces/harness/agent-tools.js";

describe("H namespace — sandbox + permissions", () => {
  it("workspaceOnly refuses paths outside the workspace", () => {
    const sb = H.workspaceOnly("/tmp/agent-sandbox");
    expect(() => sb.checkRead("/etc/passwd")).toThrow();
  });

  it("permission policy merges with deny precedence", () => {
    const allow = H.autoAllow("read_file", "bash");
    const deny = H.deny("bash");
    const merged = allow.merge(deny);
    expect(merged.decide("read_file")).toBe("allow");
    expect(merged.decide("bash")).toBe("deny");
  });
});

describe("H.todos / H.planMode", () => {
  it("TodoStore enforces single in_progress", () => {
    const store = new TodoStore();
    expect(() =>
      store.replace([
        { content: "a", activeForm: "doing a", status: "in_progress" },
        { content: "b", activeForm: "doing b", status: "in_progress" },
      ]),
    ).toThrow();
  });

  it("TodoStore round-trips items", () => {
    const store = H.todos();
    store.replace([{ content: "x", activeForm: "doing x", status: "pending" }]);
    expect(store.list()).toHaveLength(1);
    expect(store.list()[0].content).toBe("x");
  });

  it("PlanMode tracks state and identifies mutating tools", () => {
    const pm = H.planMode();
    expect(pm.current).toBe("off");
    pm.enter();
    expect(pm.current).toBe("planning");
    pm.exit("step 1; step 2");
    expect(pm.current).toBe("executing");
    expect(pm.currentPlan).toContain("step 1");
    expect(PlanMode.isMutating("write_file")).toBe(true);
    expect(PlanMode.isMutating("read_file")).toBe(false);
  });
});

describe("H.codeExecutor — polyglot runner", () => {
  let workspace: string;

  beforeAll(() => {
    workspace = mkdtempSync(join(tmpdir(), "harness-exec-"));
  });

  afterAll(() => {
    try {
      rmSync(workspace, { recursive: true, force: true });
    } catch {
      /* ignore */
    }
  });

  it("runs bash echo", async () => {
    const exec = H.codeExecutor(workspace);
    const r = await exec.run("bash", "echo hello");
    expect(r.exitCode).toBe(0);
    expect(r.stdout.trim()).toBe("hello");
  });

  it("runs node snippet", async () => {
    const exec = H.codeExecutor(workspace);
    const r = await exec.run("node", "console.log(2 + 2)");
    expect(r.exitCode).toBe(0);
    expect(r.stdout.trim()).toBe("4");
  });

  it("runs python snippet (if python3 is on PATH)", async () => {
    const exec = H.codeExecutor(workspace);
    const detected = await exec.detect();
    if (!detected.python) return;
    const r = await exec.run("python", "print('hi from py')");
    expect(r.exitCode).toBe(0);
    expect(r.stdout).toContain("hi from py");
  });

  it("respects timeout", async () => {
    const exec = H.codeExecutor(workspace);
    const r = await exec.run("bash", "sleep 5", { timeoutMs: 100 });
    expect(r.stderr).toContain("killed after");
  });

  it("refuses to run when shell is sandboxed off", async () => {
    const sb = H.sandbox({ workspace, allowShell: false });
    const exec = new (await import("../../src/namespaces/harness/code-executor.js")).CodeExecutor(
      sb,
    );
    await expect(exec.run("bash", "echo nope")).rejects.toThrow(/forbids shell/);
  });

  it("exposes run_code + which_languages tools", async () => {
    const tools = H.runCodeTools(workspace);
    expect(tools.map((t) => t.toolName)).toEqual(["run_code", "which_languages"]);
  });
});

describe("H.codingAgent — preset", () => {
  let workspace: string;

  beforeAll(() => {
    workspace = mkdtempSync(join(tmpdir(), "harness-coder-"));
    writeFileSync(join(workspace, "hello.txt"), "world");
  });

  afterAll(() => {
    try {
      rmSync(workspace, { recursive: true, force: true });
    } catch {
      /* ignore */
    }
  });

  it("returns a fully wired bundle", () => {
    const bundle = H.codingAgent(workspace, { enableGit: false });
    expect(bundle.workspace).toBe(workspace);
    expect(bundle.tools.length).toBeGreaterThan(10);
    expect(bundle.tools.map((t) => t.toolName)).toContain("read_file");
    expect(bundle.tools.map((t) => t.toolName)).toContain("run_code");
    expect(bundle.tools.map((t) => t.toolName)).toContain("todo_write");
    expect(bundle.tools.map((t) => t.toolName)).toContain("enter_plan_mode");
    expect(bundle.tools.map((t) => t.toolName)).toContain("ask_user_question");
  });

  it("read-only mode drops write/edit/exec tools", () => {
    const bundle = H.codingAgent(workspace, { allowMutations: false, enableGit: false });
    const names = bundle.tools.map((t) => t.toolName);
    expect(names).toContain("read_file");
    expect(names).not.toContain("write_file");
    expect(names).not.toContain("bash");
  });

  it("read_file tool actually reads from workspace", async () => {
    const bundle = H.codingAgent(workspace, { enableGit: false });
    const readTool = bundle.tools.find((t) => t.toolName === "read_file");
    expect(readTool).toBeDefined();
    const result = (await readTool!({ path: "hello.txt" })) as { content: string };
    expect(result.content).toBe("world");
  });
});
