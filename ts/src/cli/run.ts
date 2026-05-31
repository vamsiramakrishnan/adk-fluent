/**
 * `adk-fluent run <module:export> [--prompt TEXT]` — execute one prompt.
 *
 * Mirrors Python's `_cmd_run`: load the builder, resolve a prompt (from
 * `--prompt` or stdin), execute it, and print the response. The TypeScript
 * builder exposes execution via `.askAsync()` (preferred) or `.ask()`; we probe
 * for whichever is available and error cleanly when neither is.
 */

import { CliError, loadBuilder, type LoadedBuilder } from "./loader.js";

interface Executable {
  askAsync?: (prompt: string) => Promise<unknown>;
  ask?: (prompt: string) => unknown;
}

/** Read all of stdin as a string (used when `--prompt` is omitted). */
function readStdin(): Promise<string> {
  return new Promise((resolvePromise, reject) => {
    let data = "";
    process.stdin.setEncoding("utf8");
    process.stdin.on("data", (chunk) => (data += chunk));
    process.stdin.on("end", () => resolvePromise(data));
    process.stdin.on("error", reject);
  });
}

/** Execute one prompt against an already-loaded builder, returning its text. */
export async function runPrompt(loaded: LoadedBuilder, prompt: string): Promise<string> {
  const exec = loaded.builder as unknown as Executable;
  let response: unknown;
  if (typeof exec.askAsync === "function") {
    response = await exec.askAsync(prompt);
  } else if (typeof exec.ask === "function") {
    response = await exec.ask(prompt);
  } else {
    throw new CliError(
      `'${loaded.name}' is not executable (no .askAsync()/.ask()). ` +
        `Build it and run via the ADK CLI instead — see 'adk-fluent serve'.`,
    );
  }
  return typeof response === "string" ? response : JSON.stringify(response, null, 2);
}

/** Parse `run` args: positional target, `--prompt <text>`. */
export function parseRunArgs(args: string[]): { target?: string; prompt?: string } {
  let target: string | undefined;
  let prompt: string | undefined;
  for (let i = 0; i < args.length; i++) {
    const a = args[i];
    if (a === "--prompt") {
      prompt = args[++i];
    } else if (a.startsWith("--prompt=")) {
      prompt = a.slice("--prompt=".length);
    } else if (!a.startsWith("-") && target === undefined) {
      target = a;
    }
  }
  return { target, prompt };
}

/** CLI entry. */
export async function cmdRun(args: string[]): Promise<void> {
  const { target, prompt: promptArg } = parseRunArgs(args);
  if (!target) {
    throw new CliError("run requires a builder spec, e.g. my-agent.js:rootAgent");
  }

  let prompt = promptArg;
  if (prompt === undefined) {
    if (process.stdin.isTTY) {
      throw new CliError("provide a prompt via --prompt or stdin");
    }
    prompt = (await readStdin()).trim();
  }
  if (!prompt) {
    throw new CliError("empty prompt");
  }

  const loaded = await loadBuilder(target);
  const response = await runPrompt(loaded, prompt);
  process.stdout.write(response + "\n");
}
