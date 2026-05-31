/**
 * Shared CLI helpers — builder loading from a `module:export` spec.
 *
 * Mirrors the Python CLI's `_load_builder` / `_find_builders` helpers in
 * `adk_fluent/cli.py`. A *spec* is either:
 *
 *   module:export   — explicit named export (preferred)
 *   module.export   — dotted form, where the last segment is the export
 *   module          — auto-detect the sole builder export
 *
 * The `module` portion is resolved relative to `process.cwd()` and imported
 * dynamically (the same mechanism the `visualize` command already uses).
 */

import { resolve } from "node:path";
import { pathToFileURL } from "node:url";
import { BuilderBase } from "../core/builder-base.js";

/** A loaded builder plus the export name it was found under. */
export interface LoadedBuilder {
  name: string;
  builder: BuilderBase;
}

/** Raised for any user-facing loader failure (bad spec, missing export, …). */
export class CliError extends Error {}

/** True when `value` is a fluent builder instance (has `.build()`). */
export function isBuilder(value: unknown): value is BuilderBase {
  return value instanceof BuilderBase;
}

/**
 * Split a `module:export` / `module.export` spec into its parts.
 *
 * A `:` separator is unambiguous and always wins. Without one, the spec is
 * treated as a bare module path (auto-detect mode) — dotted module paths are
 * common (`examples/cookbook/01.ts`) so we never guess an export from a dot.
 */
export function parseSpec(spec: string): { modulePath: string; exportName?: string } {
  const colon = spec.indexOf(":");
  if (colon !== -1) {
    return {
      modulePath: spec.slice(0, colon),
      exportName: spec.slice(colon + 1) || undefined,
    };
  }
  return { modulePath: spec };
}

/** Find every builder instance exported by a module (ignoring `_`-prefixed). */
export function findBuilders(mod: Record<string, unknown>): LoadedBuilder[] {
  const out: LoadedBuilder[] = [];
  for (const [name, value] of Object.entries(mod)) {
    if (name.startsWith("_")) continue;
    if (isBuilder(value)) out.push({ name, builder: value });
  }
  return out;
}

/**
 * Import the module named by a spec. Throws {@link CliError} on failure with a
 * Node/TypeScript resolution hint (Node cannot import `.ts` natively).
 */
export async function importModule(modulePath: string): Promise<Record<string, unknown>> {
  const targetPath = resolve(process.cwd(), modulePath);
  const moduleUrl = pathToFileURL(targetPath).href;
  try {
    return (await import(moduleUrl)) as Record<string, unknown>;
  } catch (err) {
    const msg = (err as Error).message;
    let hint = "";
    if (modulePath.endsWith(".ts")) {
      hint =
        "\nHint: Node cannot resolve TypeScript imports natively. Either build " +
        "to JavaScript first and point at the .js file, or run under a TS-aware " +
        "loader (npx tsx / bun).";
    }
    throw new CliError(`could not import '${modulePath}': ${msg}${hint}`);
  }
}

/**
 * Load a single builder from a `module:export` spec.
 *
 * Mirrors Python's `_load_builder`: explicit export must exist and be a
 * builder; otherwise auto-detect the sole builder (error if none/ambiguous).
 */
export async function loadBuilder(spec: string): Promise<LoadedBuilder> {
  const { modulePath, exportName } = parseSpec(spec);
  const mod = await importModule(modulePath);

  if (exportName) {
    if (!(exportName in mod)) {
      throw new CliError(`'${exportName}' not found in ${modulePath}`);
    }
    const value = mod[exportName];
    if (!isBuilder(value)) {
      throw new CliError(`'${exportName}' is not a builder instance`);
    }
    return { name: exportName, builder: value };
  }

  const builders = findBuilders(mod);
  if (builders.length === 0) {
    throw new CliError(`no builder instances found in ${modulePath}`);
  }
  if (builders.length > 1) {
    const names = builders
      .map((b) => b.name)
      .sort()
      .join(", ");
    throw new CliError(
      `multiple builders found in ${modulePath} (${names}); ` + `specify one with 'module:export'`,
    );
  }
  return builders[0];
}
