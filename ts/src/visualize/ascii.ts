/**
 * ASCII tree renderer for the visualization IR.
 *
 * Produces a `tree`-style listing using box-drawing characters. Designed
 * for terminal output, log files, and `.explain()`-style introspection.
 */

import type { VizNode } from "./ir.js";

export interface AsciiOptions {
  /** Show tool nodes attached to agents. Defaults to `true`. */
  showTools?: boolean;
  /** Show sub-agent transfer targets. Defaults to `true`. */
  showTransfers?: boolean;
  /** Show meta info (model, instruction snippet, …). Defaults to `true`. */
  showMeta?: boolean;
  /** Truncate instruction lines at this length. Defaults to `60`. */
  maxInstructionLen?: number;
}

const TEE = "├── ";
const ELBOW = "└── ";
const PIPE = "│   ";
const SPACE = "    ";

function tag(node: VizNode): string {
  switch (node.kind) {
    case "sequence":
      return "[seq]";
    case "parallel":
      return "[par]";
    case "loop":
      return "[loop]";
    case "fallback":
      return "[fallback]";
    case "route":
      return "[route]";
    case "primitive":
      return `[${(node.meta.kind as string) ?? "prim"}]`;
    case "tool":
      return "[tool]";
    case "agent":
      return "[agent]";
    default:
      return node.source ? `[${node.source}]` : "[?]";
  }
}

function header(node: VizNode): string {
  return `${node.label} ${tag(node)}`;
}

function metaLines(node: VizNode, opts: Required<AsciiOptions>): string[] {
  if (!opts.showMeta) return [];
  const lines: string[] = [];
  if (typeof node.meta.model === "string") lines.push(`model: ${node.meta.model}`);
  if (typeof node.meta.maxIterations === "number") lines.push(`max: ${node.meta.maxIterations}`);
  if (typeof node.meta.key === "string") lines.push(`key: ${node.meta.key}`);
  if (node.guardCount > 0) lines.push(`guards: ${node.guardCount}`);
  if (typeof node.meta.instruction === "string") {
    const trimmed = node.meta.instruction.replace(/\s+/g, " ").trim();
    const truncated =
      trimmed.length > opts.maxInstructionLen
        ? trimmed.slice(0, opts.maxInstructionLen) + "…"
        : trimmed;
    lines.push(`instruct: "${truncated}"`);
  }
  return lines;
}

function childrenOf(node: VizNode, opts: Required<AsciiOptions>): VizNode[] {
  const all: VizNode[] = [];
  // Composite children come first.
  all.push(...node.children);
  // Routing branches next, with labels woven in.
  if (node.branches) {
    for (const b of node.branches) {
      all.push({ ...b.node, label: `${b.label}: ${b.node.label}` });
    }
  }
  if (node.defaultChild) {
    all.push({ ...node.defaultChild, label: `(default): ${node.defaultChild.label}` });
  }
  // Transfers and tools as virtual children so the tree stays a tree.
  if (opts.showTransfers && node.transfers.length > 0) {
    for (const t of node.transfers) {
      all.push({ ...t, label: `transfer → ${t.label}` });
    }
  }
  if (opts.showTools && node.tools.length > 0) {
    for (const t of node.tools) {
      all.push({ ...t, label: `tool: ${t.label}` });
    }
  }
  return all;
}

function renderInner(
  node: VizNode,
  prefix: string,
  isRoot: boolean,
  isLast: boolean,
  out: string[],
  opts: Required<AsciiOptions>,
): void {
  const marker = isRoot ? "" : isLast ? ELBOW : TEE;
  out.push(`${prefix}${marker}${header(node)}`);

  // Continuation prefix used by this node's meta lines and children.
  const childPrefix = prefix + (isRoot ? "" : isLast ? SPACE : PIPE);

  const kids = childrenOf(node, opts);
  const meta = metaLines(node, opts);

  // Meta lines hang under the header. They use a `·` bullet so they
  // visually distinguish from real children.
  for (const m of meta) {
    const sep = kids.length > 0 ? PIPE : SPACE;
    out.push(`${childPrefix}${sep}· ${m}`);
  }

  for (let i = 0; i < kids.length; i++) {
    const childIsLast = i === kids.length - 1;
    renderInner(kids[i], childPrefix, false, childIsLast, out, opts);
  }
}

/** Render a VizNode tree to a multi-line ASCII string. */
export function renderAscii(node: VizNode, opts: AsciiOptions = {}): string {
  const resolved: Required<AsciiOptions> = {
    showTools: opts.showTools ?? true,
    showTransfers: opts.showTransfers ?? true,
    showMeta: opts.showMeta ?? true,
    maxInstructionLen: opts.maxInstructionLen ?? 60,
  };
  const out: string[] = [];
  renderInner(node, "", true, true, out, resolved);
  return out.join("\n");
}
