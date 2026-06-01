#!/usr/bin/env node
/**
 * adk-fluent-ts CLI — top-level dispatcher.
 *
 * Mirrors the Python CLI (`adk_fluent/cli.py`) subcommand surface:
 *
 *   adk-fluent visualize <module> [--format ...] [--export ...] [-o file]
 *   adk-fluent doctor    <module:export>
 *   adk-fluent run       <module:export> [--prompt TEXT]
 *   adk-fluent new       <name> [--dir PATH]
 *   adk-fluent serve     <module:export> [--port N]
 *
 * Each subcommand lives in its own module; this file only parses the leading
 * command word, dispatches, and renders user-facing errors.
 */

import { resolve } from "node:path";
import { pathToFileURL } from "node:url";
import { cmdVisualize } from "./visualize.js";
import { cmdDoctor } from "./doctor.js";
import { cmdRun } from "./run.js";
import { cmdNew } from "./new.js";
import { cmdServe } from "./serve.js";
import { CliError } from "./loader.js";

type Handler = (args: string[]) => Promise<void>;

const COMMANDS: Record<string, Handler> = {
  visualize: cmdVisualize,
  doctor: cmdDoctor,
  run: cmdRun,
  new: cmdNew,
  serve: cmdServe,
};

function printHelp(): void {
  process.stdout.write(`adk-fluent — fluent builder API CLI (TypeScript)

Usage:
  adk-fluent <command> [options]

Commands:
  visualize <module> [--format ...] [--export ...] [-o file]
                       Render a builder topology (ascii|mermaid|markdown|json)
  doctor <module:export>
                       Print a builder's diagnostic report
  run <module:export> [--prompt TEXT]
                       Execute one prompt against a builder
  new <name> [--dir PATH]
                       Scaffold a minimal TypeScript agent project
  serve <module:export> [--port N]
                       Print the ADK command to serve a builder

Run 'adk-fluent <command> --help' for command-specific options.
`);
}

/**
 * Dispatch an argv slice (everything after the node + script path).
 * Returns the intended process exit code.
 */
export async function run(argv: string[]): Promise<number> {
  const command = argv[0];

  if (command === undefined || command === "-h" || command === "--help") {
    printHelp();
    return command === undefined ? 1 : 0;
  }

  const handler = COMMANDS[command];
  if (!handler) {
    process.stderr.write(`Error: unknown command '${command}'\n\n`);
    printHelp();
    return 1;
  }

  try {
    await handler(argv.slice(1));
    return 0;
  } catch (err) {
    if (err instanceof CliError) {
      process.stderr.write(`Error: ${err.message}\n`);
      return 1;
    }
    throw err;
  }
}

// Self-run only when invoked directly as the binary entry (not when imported
// by tests). `import.meta.url` matches argv[1] for the real entry point.
const _invokedDirectly =
  typeof process.argv[1] === "string" &&
  import.meta.url === pathToFileURL(resolve(process.argv[1])).href;
if (_invokedDirectly) {
  run(process.argv.slice(2))
    .then((code) => {
      if (code !== 0) process.exit(code);
    })
    .catch((err) => {
      process.stderr.write(`${(err as Error).stack ?? String(err)}\n`);
      process.exit(1);
    });
}
