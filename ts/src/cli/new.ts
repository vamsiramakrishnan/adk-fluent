/**
 * `adk-fluent new <name> [--dir PATH]` — scaffold a minimal TS agent project.
 *
 * Mirrors Python's `_cmd_new`, producing the TypeScript equivalent: an
 * `agent.ts` exporting a built `rootAgent`, an `index.ts` re-export, and a
 * README. Refuses to overwrite an existing directory.
 */

import { existsSync, mkdirSync, writeFileSync } from "node:fs";
import { join, resolve } from "node:path";
import { CliError } from "./loader.js";

const agentTemplate = (name: string): string => `/**
 * Minimal adk-fluent agent for ${name}.
 */
import { Agent } from "adk-fluent-ts";

// \`rootAgent\` is the conventional name ADK looks for (adk web / adk run).
export const rootAgent = new Agent("${name}", "gemini-2.5-flash")
  .instruct("You are a helpful assistant.")
  .build();
`;

const indexTemplate = (): string => `export { rootAgent } from "./agent.js";
`;

const readmeTemplate = (name: string): string => `# ${name}

A minimal [adk-fluent-ts](https://github.com/vamsiramakrishnan/adk-fluent) agent project.

## Run

    npm install adk-fluent-ts
    adk web ${name}        # or: adk run ${name}

## Develop

The agent lives in \`${name}/agent.ts\` as \`rootAgent\`. Edit it with the
fluent builder API, then re-run.

    adk-fluent doctor ${name}/agent.ts:rootAgent
    adk-fluent run ${name}/agent.ts:rootAgent --prompt "Hello"
`;

/** Create the project scaffold. Returns the list of created file paths. */
export function scaffold(name: string, dir: string): string[] {
  const base = resolve(dir, name);
  if (existsSync(base)) {
    throw new CliError(`'${base}' already exists`);
  }
  mkdirSync(base, { recursive: true });

  const created: string[] = [];
  const files: Array<[string, string]> = [
    ["agent.ts", agentTemplate(name)],
    ["index.ts", indexTemplate()],
    ["README.md", readmeTemplate(name)],
  ];
  for (const [filename, content] of files) {
    const path = join(base, filename);
    writeFileSync(path, content, "utf8");
    created.push(path);
  }
  return created;
}

/** Parse `new` args: positional name, `--dir <path>`. */
export function parseNewArgs(args: string[]): { name?: string; dir: string } {
  let name: string | undefined;
  let dir = ".";
  for (let i = 0; i < args.length; i++) {
    const a = args[i];
    if (a === "--dir") {
      dir = args[++i] ?? ".";
    } else if (a.startsWith("--dir=")) {
      dir = a.slice("--dir=".length);
    } else if (!a.startsWith("-") && name === undefined) {
      name = a;
    }
  }
  return { name, dir };
}

/** CLI entry. */
export async function cmdNew(args: string[]): Promise<void> {
  const { name, dir } = parseNewArgs(args);
  if (!name) {
    throw new CliError("new requires a project name, e.g. adk-fluent new my-agent");
  }
  const created = scaffold(name, dir);
  process.stdout.write(`Created project '${name}':\n`);
  for (const path of created) {
    process.stdout.write(`  ${path}\n`);
  }
}
