/**
 * A — Artifacts namespace.
 *
 * Artifact lifecycle management: publish, snapshot, save, load, and transforms.
 *
 * Operators (see `shared/parity.toml` for the cross-language contract):
 *   a.pipe(b)  → chain: apply a, then b in sequence. Mirrors Python
 *                `a >> b`. Every operation is order-sensitive
 *                (e.g. `A.snapshot().pipe(A.load())`).
 *   a.attachTo(builder) → equivalent to Python's `a >> builder`.
 *                         Calls `builder.artifacts(a)`.
 *
 * Artifact composites do not expose `.union()` — there is no union
 * semantic for artifacts.
 *
 * Usage:
 *   agent.artifacts(A.publish("report.md", { fromKey: "report" }))
 *   A.publish("data.json", { fromKey: "result" }).pipe(A.snapshot("data.json", { intoKey: "cached" }))
 */

import type { State, StatePredicate } from "../core/types.js";
import type { BuilderBase } from "../core/builder-base.js";
import { STransform } from "./state.js";
import { CTransform } from "./context.js";

/** Descriptor for a single artifact operation. */
export interface ArtifactSpec {
  type: string;
  config: Record<string, unknown>;
}

/** A composable artifact operation descriptor. */
export class AComposite {
  constructor(public readonly ops: ArtifactSpec[]) {}

  /** Chain: add another artifact operation. */
  pipe(other: AComposite): AComposite {
    return new AComposite([...this.ops, ...other.ops]);
  }

  /** Convert to a flat array for passing to builder. */
  toArray(): ArtifactSpec[] {
    return [...this.ops];
  }

  /**
   * Attach this artifact operation to a builder. Mirrors Python's
   * ``A.publish("report.md", from_key="draft") >> Agent(...)`` / the
   * ``Builder >> A.publish(...)`` reverse direction.
   */
  attachTo<B extends BuilderBase>(builder: B): B {
    const setter = (builder as unknown as { artifacts: (...v: unknown[]) => B }).artifacts;
    if (typeof setter !== "function") {
      throw new TypeError(
        `AComposite.attachTo: builder has no .artifacts() method (builder is ${builder.constructor.name})`,
      );
    }
    return setter.call(builder, this);
  }
}

/** MIME type constants. */
class MimeConstants {
  readonly text = "text/plain";
  readonly markdown = "text/markdown";
  readonly html = "text/html";
  readonly csv = "text/csv";
  readonly json = "application/json";
  readonly xml = "application/xml";
  readonly yaml = "application/yaml";
  readonly pdf = "application/pdf";
  readonly png = "image/png";
  readonly jpeg = "image/jpeg";
  readonly gif = "image/gif";
  readonly webp = "image/webp";
  readonly svg = "image/svg+xml";
  readonly mp3 = "audio/mpeg";
  readonly wav = "audio/wav";
  readonly ogg = "audio/ogg";
  readonly mp4 = "video/mp4";
  readonly webm = "video/webm";
  readonly binary = "application/octet-stream";
}

/** Tool factories for LLM artifact interaction. */
class ToolFactory {
  /** Create a FunctionTool for saving artifacts. */
  save(opts?: { name?: string; mime?: string; allowed?: string[]; scope?: string }): AComposite {
    return new AComposite([
      {
        type: "tool_save",
        config: {
          name: opts?.name ?? "save_artifact",
          mime: opts?.mime,
          allowed: opts?.allowed,
          scope: opts?.scope ?? "agent",
        },
      },
    ]);
  }

  /** Create a FunctionTool for loading artifacts. */
  load(opts?: { name?: string; scope?: string }): AComposite {
    return new AComposite([
      {
        type: "tool_load",
        config: {
          name: opts?.name ?? "load_artifact",
          scope: opts?.scope ?? "agent",
        },
      },
    ]);
  }

  /** Create a FunctionTool for listing artifacts. */
  list(opts?: { name?: string; scope?: string }): AComposite {
    return new AComposite([
      {
        type: "tool_list",
        config: {
          name: opts?.name ?? "list_artifacts",
          scope: opts?.scope ?? "agent",
        },
      },
    ]);
  }

  /** Create a FunctionTool for checking artifact version metadata. */
  version(opts?: { name?: string; scope?: string }): AComposite {
    return new AComposite([
      {
        type: "tool_version",
        config: {
          name: opts?.name ?? "artifact_version",
          scope: opts?.scope ?? "agent",
        },
      },
    ]);
  }
}

/**
 * A namespace — artifact lifecycle factories.
 *
 * All 17 methods + mime constants + tool sub-namespace from the Python A namespace.
 */
export class A {
  /** MIME type constants. */
  static readonly mime = new MimeConstants();

  /** Tool factories for LLM artifact interaction. */
  static readonly tool = new ToolFactory();

  // ------------------------------------------------------------------
  // Core operations (state bridges)
  // ------------------------------------------------------------------

  /** Publish state[fromKey] to an artifact file. */
  static publish(
    filename: string,
    opts?: { fromKey?: string; mime?: string; metadata?: Record<string, unknown>; scope?: string },
  ): AComposite {
    return new AComposite([
      {
        type: "publish",
        config: {
          filename,
          fromKey: opts?.fromKey ?? filename.replace(/\.[^.]+$/, ""),
          mime: opts?.mime,
          metadata: opts?.metadata,
          scope: opts?.scope ?? "agent",
        },
      },
    ]);
  }

  /** Snapshot an artifact into state[intoKey]. */
  static snapshot(
    filename: string,
    opts?: { intoKey?: string; version?: number; decode?: boolean; scope?: string },
  ): AComposite {
    return new AComposite([
      {
        type: "snapshot",
        config: {
          filename,
          intoKey: opts?.intoKey ?? filename.replace(/\.[^.]+$/, ""),
          version: opts?.version,
          decode: opts?.decode ?? true,
          scope: opts?.scope ?? "agent",
        },
      },
    ]);
  }

  /** Save literal content to an artifact (no state bridge). */
  static save(
    filename: string,
    opts?: {
      content?: string | Uint8Array;
      mime?: string;
      metadata?: Record<string, unknown>;
      scope?: string;
    },
  ): AComposite {
    return new AComposite([
      {
        type: "save",
        config: {
          filename,
          content: opts?.content,
          mime: opts?.mime,
          metadata: opts?.metadata,
          scope: opts?.scope ?? "agent",
        },
      },
    ]);
  }

  /** Load an artifact for pipeline use (no state bridge). */
  static load(filename: string, opts?: { scope?: string }): AComposite {
    return new AComposite([
      {
        type: "load",
        config: {
          filename,
          scope: opts?.scope ?? "agent",
        },
      },
    ]);
  }

  /** List artifact filenames into state[intoKey]. */
  static list(opts?: { intoKey?: string }): AComposite {
    return new AComposite([
      {
        type: "list",
        config: { intoKey: opts?.intoKey ?? "artifact_list" },
      },
    ]);
  }

  /** Get artifact version metadata into state[intoKey]. */
  static version(filename: string, opts?: { intoKey?: string }): AComposite {
    return new AComposite([
      {
        type: "version",
        config: {
          filename,
          intoKey: opts?.intoKey ?? `${filename}_version`,
        },
      },
    ]);
  }

  /** Delete all versions of an artifact. */
  static delete(filename: string): AComposite {
    return new AComposite([
      {
        type: "delete",
        config: { filename },
      },
    ]);
  }

  // ------------------------------------------------------------------
  // Batch operations
  // ------------------------------------------------------------------

  /** Batch publish multiple (filename, fromKey) pairs. */
  static publishMany(
    pairs: Array<[string, string]>,
    opts?: { mime?: string; scope?: string },
  ): AComposite {
    const ops = pairs.map(([filename, fromKey]) => ({
      type: "publish" as const,
      config: {
        filename,
        fromKey,
        mime: opts?.mime,
        scope: opts?.scope ?? "agent",
      },
    }));
    return new AComposite(ops);
  }

  /** Batch snapshot multiple (filename, intoKey) pairs. */
  static snapshotMany(pairs: Array<[string, string]>, opts?: { scope?: string }): AComposite {
    const ops = pairs.map(([filename, intoKey]) => ({
      type: "snapshot" as const,
      config: {
        filename,
        intoKey,
        scope: opts?.scope ?? "agent",
      },
    }));
    return new AComposite(ops);
  }

  // ------------------------------------------------------------------
  // Content transforms (return STransform for state pipeline use)
  // ------------------------------------------------------------------

  /** Parse JSON string in state[key] to object. */
  static asJson(key: string): STransform {
    return new STransform(
      `A.asJson(${key})`,
      (state: State) => ({
        ...state,
        [key]: typeof state[key] === "string" ? JSON.parse(state[key] as string) : state[key],
      }),
      [key],
      [key],
    );
  }

  /** Parse CSV string in state[key] to array of objects. */
  static asCsv(key: string, opts?: { columns?: string[] }): STransform {
    return new STransform(
      `A.asCsv(${key})`,
      (state: State) => {
        const raw = state[key];
        if (typeof raw !== "string") return state;
        const lines = raw.trim().split("\n");
        const headers = opts?.columns ?? (lines[0]?.split(",").map((h) => h.trim()) || []);
        const dataStart = opts?.columns ? 0 : 1;
        const rows = lines.slice(dataStart).map((line) => {
          const values = line.split(",").map((v) => v.trim());
          const row: Record<string, string> = {};
          headers.forEach((h, i) => {
            row[h] = values[i] ?? "";
          });
          return row;
        });
        return { ...state, [key]: rows };
      },
      [key],
      [key],
    );
  }

  /** Ensure state[key] is a decoded string. */
  static asText(key: string, opts?: { encoding?: string }): STransform {
    return new STransform(
      `A.asText(${key})`,
      (state: State) => {
        const val = state[key];
        if (val instanceof Uint8Array) {
          return { ...state, [key]: new TextDecoder(opts?.encoding ?? "utf-8").decode(val) };
        }
        return { ...state, [key]: String(val ?? "") };
      },
      [key],
      [key],
    );
  }

  /** Serialize state[key] object to JSON string. */
  static fromJson(key: string, opts?: { indent?: number }): STransform {
    return new STransform(
      `A.fromJson(${key})`,
      (state: State) => ({
        ...state,
        [key]: JSON.stringify(state[key], null, opts?.indent ?? 2),
      }),
      [key],
      [key],
    );
  }

  /** Serialize state[key] array of objects to CSV string. */
  static fromCsv(key: string): STransform {
    return new STransform(
      `A.fromCsv(${key})`,
      (state: State) => {
        const items = state[key];
        if (!Array.isArray(items) || items.length === 0) return state;
        const headers = Object.keys(items[0] as Record<string, unknown>);
        const rows = [
          headers.join(","),
          ...items.map((item: unknown) =>
            headers.map((h) => String((item as Record<string, unknown>)[h] ?? "")).join(","),
          ),
        ];
        return { ...state, [key]: rows.join("\n") };
      },
      [key],
      [key],
    );
  }

  /** Convert Markdown in state[key] to HTML string. */
  static fromMarkdown(key: string): STransform {
    return new STransform(
      `A.fromMarkdown(${key})`,
      (state: State) => {
        // Basic markdown→html conversion (headings, bold, italic, lists)
        const md = String(state[key] ?? "");
        const html = md
          .replace(/^### (.+)$/gm, "<h3>$1</h3>")
          .replace(/^## (.+)$/gm, "<h2>$1</h2>")
          .replace(/^# (.+)$/gm, "<h1>$1</h1>")
          .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
          .replace(/\*(.+?)\*/g, "<em>$1</em>")
          .replace(/^- (.+)$/gm, "<li>$1</li>")
          .replace(/\n/g, "<br>");
        return { ...state, [key]: html };
      },
      [key],
      [key],
    );
  }

  // ------------------------------------------------------------------
  // Conditional
  // ------------------------------------------------------------------

  /** Conditional artifact operation. */
  static when(predicate: StatePredicate, transform: AComposite): AComposite {
    return new AComposite(
      transform.ops.map((op) => ({
        ...op,
        config: { ...op.config, condition: predicate },
      })),
    );
  }

  // ------------------------------------------------------------------
  // LLM context bridge
  // ------------------------------------------------------------------

  /** Load artifact directly into LLM context (returns CTransform). */
  static forLlm(filename: string, opts?: { version?: number; scope?: string }): CTransform {
    return new CTransform(
      "artifact_for_llm",
      {
        filename,
        version: opts?.version,
        scope: opts?.scope ?? "agent",
      },
      false,
    );
  }
}
