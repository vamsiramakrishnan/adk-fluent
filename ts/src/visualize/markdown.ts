/**
 * Markdown "anatomy" renderer.
 *
 * Produces a structured markdown report that mirrors what an LLM
 * actually sees when an agent runs: instructions, tools, sub-agents,
 * guards. Useful for `.explain()` output, README diagrams, and PR
 * descriptions.
 */

import type { VizNode } from "./ir.js";
import { renderMermaid } from "./mermaid.js";

export interface MarkdownOptions {
  /** Inline a Mermaid diagram at the top of the report. Defaults to `true`. */
  includeDiagram?: boolean;
  /** Heading level for the root node (1-6). Defaults to `2`. */
  rootLevel?: number;
}

function nodeSection(node: VizNode, level: number, out: string[]): void {
  const heading = "#".repeat(Math.min(6, level));
  out.push(`${heading} ${node.label}`);
  out.push("");

  // Tag table.
  const facts: [string, string][] = [];
  if (node.source) facts.push(["type", node.source]);
  facts.push(["kind", node.kind]);
  if (typeof node.meta.model === "string") facts.push(["model", node.meta.model]);
  if (typeof node.meta.maxIterations === "number")
    facts.push(["max iterations", String(node.meta.maxIterations)]);
  if (typeof node.meta.key === "string") facts.push(["route key", node.meta.key]);
  if (node.guardCount > 0) facts.push(["guards", String(node.guardCount)]);
  if (node.tools.length > 0) facts.push(["tools", String(node.tools.length)]);
  if (node.transfers.length > 0) facts.push(["transfer targets", String(node.transfers.length)]);

  if (facts.length > 0) {
    out.push("| field | value |");
    out.push("| --- | --- |");
    for (const [k, v] of facts) out.push(`| ${k} | \`${v}\` |`);
    out.push("");
  }

  if (typeof node.meta.description === "string") {
    out.push(`> ${node.meta.description}`);
    out.push("");
  }

  if (typeof node.meta.instruction === "string") {
    out.push("**Instruction**");
    out.push("");
    out.push("```");
    out.push(node.meta.instruction);
    out.push("```");
    out.push("");
  }

  if (node.tools.length > 0) {
    out.push("**Tools**");
    out.push("");
    for (const t of node.tools) out.push(`- \`${t.name}\` _(${t.source ?? "tool"})_`);
    out.push("");
  }

  // Children sections.
  const subSections: VizNode[] = [];
  subSections.push(...node.children);
  if (node.branches) {
    for (const b of node.branches) {
      subSections.push({ ...b.node, label: `${b.label} → ${b.node.label}` });
    }
  }
  if (node.defaultChild) {
    subSections.push({ ...node.defaultChild, label: `(default) → ${node.defaultChild.label}` });
  }
  for (const t of node.transfers) {
    subSections.push({ ...t, label: `transfer: ${t.label}` });
  }

  for (const child of subSections) {
    nodeSection(child, level + 1, out);
  }
}

/** Render a VizNode tree to a markdown report. */
export function renderMarkdown(node: VizNode, opts: MarkdownOptions = {}): string {
  const includeDiagram = opts.includeDiagram ?? true;
  const rootLevel = opts.rootLevel ?? 2;

  const out: string[] = [];

  if (includeDiagram) {
    out.push("```mermaid");
    out.push(renderMermaid(node));
    out.push("```");
    out.push("");
  }

  nodeSection(node, rootLevel, out);
  return out.join("\n").trimEnd() + "\n";
}
