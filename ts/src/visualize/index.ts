/**
 * Visualization entry point.
 *
 * The single `visualize()` function dispatches on the requested format
 * and returns a string. All renderers operate on the IR produced by
 * `normalize()`, so external callers can drop in custom renderers by
 * importing the IR types and the renderer modules directly.
 */

import { normalize, type VizNode } from "./ir.js";
import { renderAscii, type AsciiOptions } from "./ascii.js";
import { renderMermaid, type MermaidOptions } from "./mermaid.js";
import { renderMarkdown, type MarkdownOptions } from "./markdown.js";

export type VisualizeFormat = "ascii" | "mermaid" | "markdown" | "json";

export interface VisualizeOptions {
  format?: VisualizeFormat;
  ascii?: AsciiOptions;
  mermaid?: MermaidOptions;
  markdown?: MarkdownOptions;
}

/**
 * Render a builder build output (or any tagged-config tree) to a string.
 *
 * Accepts the tagged config emitted by `.build()` — pass it directly:
 *
 *   const config = pipeline.build();
 *   console.log(visualize(config, { format: "mermaid" }));
 */
export function visualize(input: unknown, opts: VisualizeOptions = {}): string {
  const node = normalize(input);
  const format = opts.format ?? "ascii";

  switch (format) {
    case "ascii":
      return renderAscii(node, opts.ascii);
    case "mermaid":
      return renderMermaid(node, opts.mermaid);
    case "markdown":
      return renderMarkdown(node, opts.markdown);
    case "json":
      return JSON.stringify(node, jsonReplacer, 2);
    default: {
      const _exhaustive: never = format;
      throw new Error(`Unknown visualize format: ${String(_exhaustive)}`);
    }
  }
}

/** Strip unserialisable values (functions) from JSON output. */
function jsonReplacer(_key: string, value: unknown): unknown {
  if (typeof value === "function") return "<function>";
  return value;
}

export { normalize, renderAscii, renderMermaid, renderMarkdown };
export type { VizNode, AsciiOptions, MermaidOptions, MarkdownOptions };
