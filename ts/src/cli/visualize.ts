#!/usr/bin/env node
/**
 * `adk-fluent visualize` — render a builder topology to ascii, mermaid,
 * or markdown.
 *
 * Usage
 * -----
 *   adk-fluent visualize <module.ts> [--format=ascii|mermaid|markdown|json]
 *                                    [--export=<name>]
 *                                    [-o <file>]
 *
 * The target module is dynamically imported. Every exported value that
 * looks like a tagged-config tree (`{ _type: "..." }`) is rendered. If
 * `--export=<name>` is provided, only that named export is used.
 *
 * Examples
 * --------
 *   adk-fluent visualize examples/cookbook/04_sequential_pipeline.ts
 *   adk-fluent visualize my-agent.ts --format=mermaid -o diagram.md
 *   adk-fluent visualize my-agent.ts --export=pipeline --format=markdown
 */

import { writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { pathToFileURL } from "node:url";
import { visualize, type VisualizeFormat } from "../visualize/index.js";

interface ParsedArgs {
  target?: string;
  format: VisualizeFormat;
  exportName?: string;
  output?: string;
  help: boolean;
}

function parseArgs(argv: string[]): ParsedArgs {
  const out: ParsedArgs = { format: "ascii", help: false };
  for (let i = 0; i < argv.length; i++) {
    const arg = argv[i];
    if (arg === "-h" || arg === "--help") {
      out.help = true;
    } else if (arg === "-o" || arg === "--output") {
      out.output = argv[++i];
    } else if (arg.startsWith("--format=")) {
      out.format = arg.slice("--format=".length) as VisualizeFormat;
    } else if (arg === "--format") {
      out.format = argv[++i] as VisualizeFormat;
    } else if (arg.startsWith("--export=")) {
      out.exportName = arg.slice("--export=".length);
    } else if (arg === "--export") {
      out.exportName = argv[++i];
    } else if (!out.target) {
      out.target = arg;
    }
  }
  return out;
}

function printHelp(): void {
  process.stdout.write(`adk-fluent visualize — render a builder topology

Usage:
  adk-fluent visualize <module.ts> [options]

Options:
  --format <fmt>     ascii | mermaid | markdown | json   (default: ascii)
  --export <name>    Render only the named export
  -o, --output <f>   Write output to file instead of stdout
  -h, --help         Show this help

Examples:
  adk-fluent visualize examples/cookbook/04_sequential_pipeline.ts
  adk-fluent visualize my-agent.ts --format=mermaid -o diagram.md
`);
}

function looksLikeTaggedConfig(value: unknown): boolean {
  return (
    typeof value === "object" &&
    value !== null &&
    typeof (value as { _type?: unknown })._type === "string"
  );
}

async function main(): Promise<void> {
  const args = parseArgs(process.argv.slice(2));

  if (args.help || !args.target) {
    printHelp();
    process.exit(args.help ? 0 : 1);
  }

  const targetPath = resolve(process.cwd(), args.target);
  const moduleUrl = pathToFileURL(targetPath).href;

  let mod: Record<string, unknown>;
  try {
    mod = (await import(moduleUrl)) as Record<string, unknown>;
  } catch (err) {
    const msg = (err as Error).message;
    process.stderr.write(`Failed to import ${args.target}: ${msg}\n`);
    if (args.target.endsWith(".ts")) {
      process.stderr.write(
        "\nHint: Node cannot resolve TypeScript imports natively. Either\n" +
          "  • build to JavaScript first and point at the .js file, or\n" +
          "  • run under a TS-aware loader:\n" +
          "      npx tsx node_modules/adk-fluent-ts/dist/cli/visualize.js " +
          args.target +
          "\n" +
          "      bun node_modules/adk-fluent-ts/dist/cli/visualize.js " +
          args.target +
          "\n",
      );
    }
    process.exit(1);
  }

  const renderables: { name: string; value: unknown }[] = [];
  if (args.exportName) {
    if (!(args.exportName in mod)) {
      process.stderr.write(`Export '${args.exportName}' not found in ${args.target}\n`);
      process.exit(1);
    }
    renderables.push({ name: args.exportName, value: mod[args.exportName] });
  } else {
    for (const [name, value] of Object.entries(mod)) {
      if (looksLikeTaggedConfig(value)) {
        renderables.push({ name, value });
      }
    }
  }

  if (renderables.length === 0) {
    process.stderr.write(
      `No tagged-config exports found in ${args.target}. ` +
        `Make sure your module exports a value produced by .build().\n`,
    );
    process.exit(1);
  }

  const sections: string[] = [];
  for (const { name, value } of renderables) {
    sections.push(`# ${name}`);
    sections.push("");
    sections.push(visualize(value, { format: args.format }));
    sections.push("");
  }
  const output = sections.join("\n");

  if (args.output) {
    writeFileSync(args.output, output, "utf8");
    process.stderr.write(`Wrote ${args.output}\n`);
  } else {
    process.stdout.write(output + "\n");
  }
}

main().catch((err) => {
  process.stderr.write(`${(err as Error).stack ?? String(err)}\n`);
  process.exit(1);
});
