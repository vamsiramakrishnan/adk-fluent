/**
 * Tests for the adk-fluent-ts CLI subcommands (Feature #10 parity port).
 *
 * Covers the top-level dispatcher (`run`), the `new` scaffolder, the builder
 * loader (`loadBuilder` / `parseSpec`), and the pure cores of `doctor` /
 * `run` / `serve`. No real LLM or network calls: execution is exercised with a
 * stub builder, and `loadBuilder` is exercised against a temp `.ts` fixture
 * that imports the in-repo source.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { existsSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { run } from "../../src/cli/index.js";
import { parseSpec, loadBuilder, findBuilders, CliError } from "../../src/cli/loader.js";
import { scaffold, parseNewArgs } from "../../src/cli/new.js";
import { diagnoseBuilder } from "../../src/cli/doctor.js";
import { runPrompt, parseRunArgs } from "../../src/cli/run.js";
import { serveGuidance, parseServeArgs } from "../../src/cli/serve.js";
import { Agent } from "../../src/builders/agent.js";

const HERE = resolve(fileURLToPath(import.meta.url), "..");
// Absolute path to the package source entry, for temp-fixture imports.
const SRC_INDEX = resolve(HERE, "../../src/index.ts");

let tmp: string;

beforeEach(() => {
  tmp = mkdtempSync(join(tmpdir(), "adk-cli-"));
});

afterEach(() => {
  rmSync(tmp, { recursive: true, force: true });
});

// --------------------------------------------------------------------------
// loader
// --------------------------------------------------------------------------

describe("parseSpec()", () => {
  it("splits a module:export spec", () => {
    expect(parseSpec("foo/bar.js:rootAgent")).toEqual({
      modulePath: "foo/bar.js",
      exportName: "rootAgent",
    });
  });

  it("treats a bare dotted path as a module (no export guess)", () => {
    expect(parseSpec("foo/bar.ts")).toEqual({ modulePath: "foo/bar.ts" });
  });
});

describe("findBuilders()", () => {
  it("collects builder instances and skips underscored / non-builders", () => {
    const mod = {
      rootAgent: new Agent("a", "gemini-2.5-flash"),
      other: new Agent("b", "gemini-2.5-flash"),
      _hidden: new Agent("c", "gemini-2.5-flash"),
      notABuilder: 42,
    };
    const found = findBuilders(mod as Record<string, unknown>);
    expect(found.map((f) => f.name).sort()).toEqual(["other", "rootAgent"]);
  });
});

describe("loadBuilder()", () => {
  it("loads a named export from a temp .ts fixture", async () => {
    const fixture = join(tmp, "agent.ts");
    writeFileSync(
      fixture,
      `import { Agent } from ${JSON.stringify(SRC_INDEX)};\n` +
        `export const rootAgent = new Agent("fixture", "gemini-2.5-flash").instruct("Hi.");\n`,
    );
    const loaded = await loadBuilder(`${fixture}:rootAgent`);
    expect(loaded.name).toBe("rootAgent");
    expect(loaded.builder.name).toBe("fixture");
  });

  it("auto-detects the sole builder when no export is given", async () => {
    const fixture = join(tmp, "solo.ts");
    writeFileSync(
      fixture,
      `import { Agent } from ${JSON.stringify(SRC_INDEX)};\n` +
        `export const onlyAgent = new Agent("solo", "gemini-2.5-flash");\n`,
    );
    const loaded = await loadBuilder(fixture);
    expect(loaded.name).toBe("onlyAgent");
  });

  it("errors when the named export is missing", async () => {
    const fixture = join(tmp, "missing.ts");
    writeFileSync(
      fixture,
      `import { Agent } from ${JSON.stringify(SRC_INDEX)};\n` +
        `export const rootAgent = new Agent("x", "gemini-2.5-flash");\n`,
    );
    await expect(loadBuilder(`${fixture}:nope`)).rejects.toBeInstanceOf(CliError);
  });

  it("errors on ambiguous multi-builder modules", async () => {
    const fixture = join(tmp, "ambiguous.ts");
    writeFileSync(
      fixture,
      `import { Agent } from ${JSON.stringify(SRC_INDEX)};\n` +
        `export const a = new Agent("a", "gemini-2.5-flash");\n` +
        `export const b = new Agent("b", "gemini-2.5-flash");\n`,
    );
    await expect(loadBuilder(fixture)).rejects.toThrow(/multiple builders/);
  });
});

// --------------------------------------------------------------------------
// new (scaffold)
// --------------------------------------------------------------------------

describe("scaffold()", () => {
  it("creates agent.ts, index.ts and README.md", () => {
    const created = scaffold("my-agent", tmp);
    const base = join(tmp, "my-agent");
    expect(existsSync(join(base, "agent.ts"))).toBe(true);
    expect(existsSync(join(base, "index.ts"))).toBe(true);
    expect(existsSync(join(base, "README.md"))).toBe(true);
    expect(created).toHaveLength(3);

    const agent = readFileSync(join(base, "agent.ts"), "utf8");
    expect(agent).toContain("export const rootAgent");
    expect(agent).toContain('new Agent("my-agent"');
    expect(agent).toContain(".build()");

    const index = readFileSync(join(base, "index.ts"), "utf8");
    expect(index).toContain('export { rootAgent } from "./agent.js"');
  });

  it("refuses to overwrite an existing directory", () => {
    scaffold("dup", tmp);
    expect(() => scaffold("dup", tmp)).toThrow(CliError);
  });

  it("parseNewArgs reads name and --dir", () => {
    expect(parseNewArgs(["proj", "--dir", "/tmp/x"])).toEqual({ name: "proj", dir: "/tmp/x" });
    expect(parseNewArgs(["proj", "--dir=/tmp/y"])).toEqual({ name: "proj", dir: "/tmp/y" });
    expect(parseNewArgs([])).toEqual({ name: undefined, dir: "." });
  });
});

// --------------------------------------------------------------------------
// doctor
// --------------------------------------------------------------------------

describe("diagnoseBuilder()", () => {
  it("prefers a builder's .doctor() when present", () => {
    const builder = { doctor: () => "DOCTOR REPORT" } as unknown as Agent;
    const out = diagnoseBuilder({ name: "x", builder });
    expect(out).toBe("DOCTOR REPORT");
  });

  it("falls back to .diagnose() then .validate()", () => {
    const diag = { diagnose: () => "DIAG" } as unknown as Agent;
    expect(diagnoseBuilder({ name: "x", builder: diag })).toBe("DIAG");

    const validated = vi.fn();
    const val = { validate: validated } as unknown as Agent;
    expect(diagnoseBuilder({ name: "x", builder: val })).toMatch(/validated/);
    expect(validated).toHaveBeenCalled();
  });

  it("falls back to inspect()/visualize() for a real builder", () => {
    const builder = new Agent("checkme", "gemini-2.5-flash").instruct("Hi.");
    const out = diagnoseBuilder({ name: "checkme", builder });
    expect(out).toContain("# checkme");
    expect(out).toContain("## config");
    expect(out).toContain("## topology");
    expect(out).toContain("checkme");
  });
});

// --------------------------------------------------------------------------
// run
// --------------------------------------------------------------------------

describe("runPrompt()", () => {
  it("calls askAsync and returns the response", async () => {
    const askAsync = vi.fn(async (p: string) => `echo:${p}`);
    const builder = { askAsync } as unknown as Agent;
    const out = await runPrompt({ name: "x", builder }, "hello");
    expect(out).toBe("echo:hello");
    expect(askAsync).toHaveBeenCalledWith("hello");
  });

  it("falls back to ask() when askAsync is absent", async () => {
    const ask = vi.fn((p: string) => `sync:${p}`);
    const builder = { ask } as unknown as Agent;
    expect(await runPrompt({ name: "x", builder }, "hi")).toBe("sync:hi");
  });

  it("errors cleanly when the builder is not executable", async () => {
    const builder = new Agent("noexec", "gemini-2.5-flash");
    await expect(runPrompt({ name: "noexec", builder }, "hi")).rejects.toBeInstanceOf(CliError);
  });

  it("parseRunArgs reads target and --prompt", () => {
    expect(parseRunArgs(["m.js:x", "--prompt", "hey"])).toEqual({
      target: "m.js:x",
      prompt: "hey",
    });
    expect(parseRunArgs(["m.js:x", "--prompt=yo"])).toEqual({ target: "m.js:x", prompt: "yo" });
    expect(parseRunArgs(["m.js:x"])).toEqual({ target: "m.js:x", prompt: undefined });
  });
});

// --------------------------------------------------------------------------
// serve
// --------------------------------------------------------------------------

describe("serve", () => {
  it("prints adk web / adk run guidance with the port", () => {
    const out = serveGuidance("agents/my-agent.ts", 9000);
    expect(out).toContain("adk web agents");
    expect(out).toContain("--port 9000");
    expect(out).toContain("adk run agents");
  });

  it("parseServeArgs defaults the port to 8000", () => {
    expect(parseServeArgs(["m.js:x"])).toEqual({ target: "m.js:x", port: 8000 });
    expect(parseServeArgs(["m.js:x", "--port", "1234"])).toEqual({ target: "m.js:x", port: 1234 });
    expect(parseServeArgs(["m.js:x", "--port=5678"])).toEqual({ target: "m.js:x", port: 5678 });
  });
});

// --------------------------------------------------------------------------
// dispatcher
// --------------------------------------------------------------------------

describe("run() dispatcher", () => {
  let outSpy: ReturnType<typeof vi.spyOn>;
  let errSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    outSpy = vi.spyOn(process.stdout, "write").mockImplementation(() => true);
    errSpy = vi.spyOn(process.stderr, "write").mockImplementation(() => true);
  });

  afterEach(() => {
    outSpy.mockRestore();
    errSpy.mockRestore();
  });

  it("--help prints usage and exits 0", async () => {
    const code = await run(["--help"]);
    expect(code).toBe(0);
    const printed = outSpy.mock.calls.map((c) => String(c[0])).join("");
    expect(printed).toContain("Usage:");
    expect(printed).toContain("visualize");
    expect(printed).toContain("doctor");
    expect(printed).toContain("serve");
  });

  it("no command prints help and exits 1", async () => {
    const code = await run([]);
    expect(code).toBe(1);
  });

  it("unknown command errors and exits 1", async () => {
    const code = await run(["frobnicate"]);
    expect(code).toBe(1);
    const printed = errSpy.mock.calls.map((c) => String(c[0])).join("");
    expect(printed).toContain("unknown command 'frobnicate'");
  });

  it("dispatches `new` and creates files, exiting 0", async () => {
    const code = await run(["new", "viaDispatch", "--dir", tmp]);
    expect(code).toBe(0);
    expect(existsSync(join(tmp, "viaDispatch", "agent.ts"))).toBe(true);
  });

  it("renders CliError from a subcommand as Error: ... and exits 1", async () => {
    // `new` with no name throws a CliError.
    const code = await run(["new"]);
    expect(code).toBe(1);
    const printed = errSpy.mock.calls.map((c) => String(c[0])).join("");
    expect(printed).toContain("Error:");
  });
});
