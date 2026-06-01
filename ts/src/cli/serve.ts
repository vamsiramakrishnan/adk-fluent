/**
 * `adk-fluent serve <module:export> [--port N]` — print ADK CLI serve guidance.
 *
 * Mirrors Python's `_cmd_serve`. adk-fluent-ts builders compile to native
 * @google/adk objects, so the ADK CLI serves them directly. We validate the
 * target loads (fail fast on a bad spec), then print the commands to run. No
 * long-running server is started here.
 */

import { CliError, loadBuilder } from "./loader.js";

/** Build the serve-guidance text for a loaded module path + port. */
export function serveGuidance(modulePath: string, port: number): string {
  // Strip a trailing file extension to get a directory-ish hint.
  const hint = modulePath.replace(/\/[^/]*\.(t|j)s$/, "") || modulePath;
  return [
    "adk-fluent-ts agents build to native @google/adk objects, so the ADK CLI serves them directly.",
    "",
    "To serve a web UI:",
    `  adk web ${hint} --port ${port}`,
    "",
    "To run interactively in the terminal:",
    `  adk run ${hint}`,
    "",
    "Note: the target module must expose a `rootAgent` (built ADK object) for the ADK CLI to discover it.",
  ].join("\n");
}

/** Parse `serve` args: positional target, `--port <n>`. */
export function parseServeArgs(args: string[]): { target?: string; port: number } {
  let target: string | undefined;
  let port = 8000;
  for (let i = 0; i < args.length; i++) {
    const a = args[i];
    if (a === "--port") {
      port = Number(args[++i]);
    } else if (a.startsWith("--port=")) {
      port = Number(a.slice("--port=".length));
    } else if (!a.startsWith("-") && target === undefined) {
      target = a;
    }
  }
  if (!Number.isFinite(port)) port = 8000;
  return { target, port };
}

/** CLI entry. */
export async function cmdServe(args: string[]): Promise<void> {
  const { target, port } = parseServeArgs(args);
  if (!target) {
    throw new CliError("serve requires a builder spec, e.g. my-agent.js:rootAgent");
  }
  // Validate the target loads — fail fast on a bad spec.
  await loadBuilder(target);
  const modulePath = target.split(":")[0];
  process.stdout.write(serveGuidance(modulePath, port) + "\n");
}
