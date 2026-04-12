/**
 * Mermaid `flowchart TD` renderer for the visualization IR.
 *
 * Output is a self-contained code block — paste it into a markdown
 * file, GitHub PR description, or mermaid.live and it renders.
 */

import type { VizNode } from "./ir.js";

export interface MermaidOptions {
  /** Include tool nodes attached to agents. Defaults to `true`. */
  showTools?: boolean;
  /** Include sub-agent transfer edges. Defaults to `true`. */
  showTransfers?: boolean;
  /** Wrap output in a fenced ```mermaid``` block. Defaults to `false`. */
  fenced?: boolean;
}

interface Emitter {
  lines: string[];
  nextId: number;
  push(line: string): void;
  id(): string;
}

function makeEmitter(): Emitter {
  return {
    lines: [],
    nextId: 0,
    push(line: string) {
      this.lines.push(line);
    },
    id() {
      return `n${this.nextId++}`;
    },
  };
}

const SHAPES: Record<VizNode["kind"], [string, string]> = {
  agent: ["[", "]"],
  sequence: ["[[", "]]"],
  parallel: ["[/", "/]"],
  loop: ["[(", ")]"],
  fallback: ["{{", "}}"],
  route: ["{", "}"],
  primitive: ["[\\", "/]"],
  tool: ["([", "])"],
  unknown: ["[", "]"],
};

function escape(label: string): string {
  return label.replace(/"/g, "&quot;").replace(/\n/g, " ").replace(/\|/g, "&#124;").slice(0, 80);
}

function emitNode(node: VizNode, emitter: Emitter, opts: Required<MermaidOptions>): string {
  const id = emitter.id();
  const [open, close] = SHAPES[node.kind] ?? SHAPES.unknown;
  emitter.push(`  ${id}${open}"${escape(node.label)}"${close}`);

  // Composite children — solid arrows.
  for (const child of node.children) {
    const childId = emitNode(child, emitter, opts);
    emitter.push(`  ${id} --> ${childId}`);
  }

  // Routing branches — labelled arrows.
  if (node.branches) {
    for (const branch of node.branches) {
      const branchId = emitNode(branch.node, emitter, opts);
      emitter.push(`  ${id} -- "${escape(branch.label)}" --> ${branchId}`);
    }
  }
  if (node.defaultChild) {
    const defaultId = emitNode(node.defaultChild, emitter, opts);
    emitter.push(`  ${id} -- "(default)" --> ${defaultId}`);
  }

  // Sub-agent transfer edges — dashed arrows.
  if (opts.showTransfers) {
    for (const t of node.transfers) {
      const tid = emitNode(t, emitter, opts);
      emitter.push(`  ${id} -.->|transfer| ${tid}`);
    }
  }

  // Tool attachments — dotted arrows.
  if (opts.showTools && node.tools.length > 0) {
    for (const t of node.tools) {
      const tid = emitter.id();
      emitter.push(`  ${tid}([${escape(t.label)}])`);
      emitter.push(`  ${id} -. tool .-> ${tid}`);
    }
  }

  return id;
}

/** Render a VizNode tree to a Mermaid `flowchart TD` source string. */
export function renderMermaid(node: VizNode, opts: MermaidOptions = {}): string {
  const resolved: Required<MermaidOptions> = {
    showTools: opts.showTools ?? true,
    showTransfers: opts.showTransfers ?? true,
    fenced: opts.fenced ?? false,
  };
  const emitter = makeEmitter();
  emitter.push("flowchart TD");
  emitNode(node, emitter, resolved);
  const body = emitter.lines.join("\n");
  return resolved.fenced ? `\`\`\`mermaid\n${body}\n\`\`\`` : body;
}
