/**
 * `adk-fluent doctor <module:export>` — load a builder and print diagnostics.
 *
 * Mirrors Python's `_cmd_doctor`, which prefers `.doctor()`, falls back to
 * `.diagnose()`, then `.validate()`. The TypeScript builder surface does not
 * (yet) expose those, so we probe for them at runtime and finally fall back to
 * the always-present `.inspect()` snapshot plus an ascii topology.
 */

import { CliError, loadBuilder, type LoadedBuilder } from "./loader.js";

interface Probe {
  doctor?: () => unknown;
  diagnose?: () => unknown;
  validate?: () => unknown;
}

/** Run the doctor diagnostics for an already-loaded builder; return the report text. */
export function diagnoseBuilder(loaded: LoadedBuilder): string {
  const builder = loaded.builder;
  const probe = builder as unknown as Probe;

  if (typeof probe.doctor === "function") {
    // .doctor() conventionally prints/returns a formatted report.
    const out = probe.doctor();
    return typeof out === "string" ? out : "OK: doctor() completed.";
  }

  if (typeof probe.diagnose === "function") {
    const out = probe.diagnose();
    return typeof out === "string" ? out : JSON.stringify(out, null, 2);
  }

  if (typeof probe.validate === "function") {
    probe.validate();
    return "OK: builder validated with no errors.";
  }

  // Fallback: always-available introspection. Build to surface any errors,
  // then print the config snapshot and an ascii topology.
  builder.build();
  const lines: string[] = [];
  lines.push(`# ${loaded.name}`);
  lines.push("");
  lines.push("## config");
  const snapshot = builder.inspect();
  for (const [k, v] of Object.entries(snapshot)) {
    lines.push(`  ${k}: ${formatValue(v)}`);
  }
  lines.push("");
  lines.push("## topology");
  lines.push(builder.visualize({ format: "ascii" }));
  lines.push("");
  lines.push("OK: builder built with no errors.");
  return lines.join("\n");
}

function formatValue(value: unknown): string {
  if (typeof value === "string") return value;
  if (value === null || value === undefined) return String(value);
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}

/** CLI entry: load the spec, diagnose, print. */
export async function cmdDoctor(args: string[]): Promise<void> {
  const target = args.find((a) => !a.startsWith("-"));
  if (!target) {
    throw new CliError("doctor requires a builder spec, e.g. my-agent.js:rootAgent");
  }
  const loaded = await loadBuilder(target);
  process.stdout.write(diagnoseBuilder(loaded) + "\n");
}
