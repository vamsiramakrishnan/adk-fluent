// flux:scaffold-user
/**
 * FluxMarkdown — prose block renderer.
 *
 * The spec promises the renderer sanitises HTML. We implement a tiny
 * tokenizer that recognises paragraphs, headings (#, ##, ###), bold
 * (``**x**``), italic (``*x*``), inline code (``` `x` ```), fenced code
 * blocks (```` ``` ````), and links (``[text](url)``). Raw HTML is
 * stripped via text escaping. This is *not* a CommonMark implementation —
 * it is a ~50-LOC safe subset that covers every example in the spec.
 */

import * as React from "react";
import type { CSSProperties, ReactElement, ReactNode } from "react";
import { asFluxElement, tokenVar } from "./_shared.js";
import type {
  FluxElement,
  FluxNode,
  FluxRenderContext,
  FluxRenderer,
} from "./types.js";

type Size = "sm" | "md" | "lg";
type ProseStyle = "compact" | "default" | "spacious";

const SIZE_FONT: Record<Size, string> = {
  sm: tokenVar("typography.size.sm"),
  md: tokenVar("typography.size.md"),
  lg: tokenVar("typography.size.lg"),
};

const PROSE_SPACING: Record<ProseStyle, { para: string; heading: string; lineHeight: string }> = {
  compact: {
    para: tokenVar("space.2"),
    heading: tokenVar("space.3"),
    lineHeight: tokenVar("typography.lineHeight.normal"),
  },
  default: {
    para: tokenVar("space.3"),
    heading: tokenVar("space.4"),
    lineHeight: tokenVar("typography.lineHeight.normal"),
  },
  spacious: {
    para: tokenVar("space.4"),
    heading: tokenVar("space.4"),
    lineHeight: tokenVar("typography.lineHeight.relaxed"),
  },
};

/**
 * Inline tokenizer — walks a single line and yields ReactNode segments.
 * Order of precedence: code span → bold → italic → link → plain text.
 */
function renderInline(text: string, keyPrefix: string): ReactNode[] {
  const nodes: ReactNode[] = [];
  let i = 0;
  let idx = 0;
  const pattern = /(`([^`]+)`)|(\*\*([^*]+)\*\*)|(\*([^*]+)\*)|(\[([^\]]+)\]\(([^)]+)\))/g;
  let match: RegExpExecArray | null;
  let lastIndex = 0;
  while ((match = pattern.exec(text)) !== null) {
    if (match.index > lastIndex) {
      nodes.push(text.slice(lastIndex, match.index));
    }
    const key = `${keyPrefix}-${i}`;
    if (match[1] !== undefined) {
      nodes.push(
        React.createElement(
          "code",
          {
            key,
            style: {
              fontFamily: tokenVar("typography.family.mono"),
              backgroundColor: tokenVar("color.bg.subtle"),
              paddingInline: tokenVar("space.1"),
              borderRadius: tokenVar("radius.xs"),
              fontSize: "0.9em",
            },
          },
          match[2],
        ),
      );
    } else if (match[3] !== undefined) {
      nodes.push(
        React.createElement("strong", { key, style: { fontWeight: 600 } }, match[4]),
      );
    } else if (match[5] !== undefined) {
      nodes.push(
        React.createElement("em", { key, style: { fontStyle: "italic" } }, match[6]),
      );
    } else if (match[7] !== undefined) {
      nodes.push(
        React.createElement(
          "a",
          {
            key,
            href: match[9],
            style: { color: tokenVar("color.text.link"), textDecoration: "underline" },
          },
          match[8],
        ),
      );
    }
    i += 1;
    lastIndex = match.index + match[0].length;
    idx = lastIndex;
  }
  if (idx < text.length) {
    nodes.push(text.slice(idx));
  }
  return nodes;
}

/** Block-level tokenizer. */
function renderBlocks(source: string, style: CSSProperties): ReactElement[] {
  const lines = source.replace(/\r\n?/g, "\n").split("\n");
  const blocks: ReactElement[] = [];
  let i = 0;
  let pIdx = 0;
  while (i < lines.length) {
    const line = lines[i]!;
    // Fenced code block
    if (line.trim().startsWith("```")) {
      const buf: string[] = [];
      i += 1;
      while (i < lines.length && !lines[i]!.trim().startsWith("```")) {
        buf.push(lines[i]!);
        i += 1;
      }
      i += 1; // skip the closing fence
      blocks.push(
        React.createElement(
          "pre",
          {
            key: `md-code-${pIdx}`,
            style: {
              fontFamily: tokenVar("typography.family.mono"),
              backgroundColor: tokenVar("color.bg.subtle"),
              padding: tokenVar("space.3"),
              borderRadius: tokenVar("radius.md"),
              overflow: "auto",
              marginBlockEnd: style.marginBlockEnd,
            },
          },
          React.createElement("code", null, buf.join("\n")),
        ),
      );
      pIdx += 1;
      continue;
    }
    // Headings
    const h = /^(#{1,3})\s+(.*)$/.exec(line);
    if (h) {
      const level = h[1]!.length;
      const tag = `h${level}`;
      blocks.push(
        React.createElement(
          tag,
          {
            key: `md-h-${pIdx}`,
            style: {
              marginBlockStart: style.marginBlockStart,
              marginBlockEnd: style.marginBlockEnd,
              fontSize: level === 1 ? tokenVar("typography.size.2xl") : level === 2 ? tokenVar("typography.size.xl") : tokenVar("typography.size.lg"),
              fontWeight: 600,
              lineHeight: style.lineHeight,
            },
          },
          ...renderInline(h[2]!, `md-h-${pIdx}-inline`),
        ),
      );
      pIdx += 1;
      i += 1;
      continue;
    }
    // Paragraph — accumulate until a blank line.
    const buf: string[] = [];
    while (i < lines.length && lines[i]!.trim() !== "" && !lines[i]!.trim().startsWith("```") && !/^#{1,3}\s+/.test(lines[i]!)) {
      buf.push(lines[i]!);
      i += 1;
    }
    const text = buf.join(" ").trim();
    if (text.length > 0) {
      blocks.push(
        React.createElement(
          "p",
          {
            key: `md-p-${pIdx}`,
            style: {
              marginBlockEnd: style.marginBlockEnd,
              lineHeight: style.lineHeight,
            },
          },
          ...renderInline(text, `md-p-${pIdx}-inline`),
        ),
      );
      pIdx += 1;
    }
    // Skip the blank line
    while (i < lines.length && lines[i]!.trim() === "") i += 1;
  }
  return blocks;
}

const FluxMarkdown: FluxRenderer = (
  node: FluxNode,
  _ctx: FluxRenderContext,
): FluxElement => {
  const size = (node.size as Size) ?? "md";
  const proseStyle = (node.proseStyle as ProseStyle) ?? "default";
  const source = typeof node.source === "string" ? node.source : "";
  const a11y = (node.accessibility as { label?: string }) ?? {};
  const spacing = PROSE_SPACING[proseStyle];

  const rootStyle: CSSProperties = {
    fontFamily: tokenVar("typography.family.sans"),
    color: tokenVar("color.text.primary"),
    fontSize: SIZE_FONT[size],
    lineHeight: spacing.lineHeight,
  };

  const blockStyle: CSSProperties = {
    marginBlockEnd: spacing.para,
    marginBlockStart: spacing.heading,
    lineHeight: spacing.lineHeight,
  };

  const blocks = renderBlocks(source, blockStyle);

  const wrapper = React.createElement(
    "div",
    {
      id: node.id,
      "aria-label": a11y.label,
      "data-flux-component": "FluxMarkdown",
      "data-flux-size": size,
      "data-flux-prose": proseStyle,
      style: rootStyle,
    },
    ...blocks,
  );
  return asFluxElement(wrapper);
};

export default FluxMarkdown;
