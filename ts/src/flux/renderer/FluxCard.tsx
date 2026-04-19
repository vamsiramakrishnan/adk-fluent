// flux:scaffold-user
/**
 * FluxCard — surface container with optional header, required body, and
 * optional footer. Variants: emphasis (subtle/outline/elevated) × padding
 * (sm/md/lg). compoundVariant: ``emphasis=outline + padding=lg`` bumps
 * border-radius and adds a subtle shadow.
 */

import * as React from "react";
import type { CSSProperties } from "react";
import { asFluxElement, mergeStyles, renderSlot, tokenVar } from "./_shared.js";
import type {
  FluxElement,
  FluxNode,
  FluxRenderContext,
  FluxRenderer,
} from "./types.js";

type Emphasis = "subtle" | "outline" | "elevated";
type Padding = "sm" | "md" | "lg";

const EMPHASIS_STYLE: Record<Emphasis, CSSProperties> = {
  subtle: {
    backgroundColor: tokenVar("color.bg.subtle"),
    borderWidth: "0px",
    borderStyle: "solid",
    boxShadow: "none",
    borderRadius: tokenVar("radius.md"),
  },
  outline: {
    backgroundColor: tokenVar("color.bg.surface"),
    borderWidth: "1px",
    borderStyle: "solid",
    borderColor: tokenVar("color.border.default"),
    boxShadow: "none",
    borderRadius: tokenVar("radius.md"),
  },
  elevated: {
    backgroundColor: tokenVar("color.bg.surface"),
    borderWidth: "0px",
    borderStyle: "solid",
    boxShadow: tokenVar("shadow.md"),
    borderRadius: tokenVar("radius.lg"),
  },
};

const PADDING_STYLE: Record<Padding, CSSProperties> = {
  sm: {
    paddingBlock: tokenVar("space.3"),
    paddingInline: tokenVar("space.3"),
  },
  md: {
    paddingBlock: tokenVar("space.4"),
    paddingInline: tokenVar("space.4"),
  },
  lg: {
    paddingBlock: tokenVar("space.6"),
    paddingInline: tokenVar("space.6"),
  },
};

const FluxCard: FluxRenderer = (
  node: FluxNode,
  ctx: FluxRenderContext,
): FluxElement => {
  const emphasis = (node.emphasis as Emphasis) ?? "subtle";
  const padding = (node.padding as Padding) ?? "md";
  const a11y = (node.accessibility as { label?: string }) ?? {};

  const style = mergeStyles(
    {
      display: "flex",
      flexDirection: "column",
      gap: tokenVar("space.3"),
      fontFamily: tokenVar("typography.family.sans"),
      color: tokenVar("color.text.primary"),
    },
    EMPHASIS_STYLE[emphasis],
    PADDING_STYLE[padding],
    emphasis === "outline" && padding === "lg"
      ? { borderRadius: tokenVar("radius.xl"), boxShadow: tokenVar("shadow.sm") }
      : undefined,
  );

  const header = renderSlot(node.header, ctx, node.id, "header");
  const body = renderSlot(node.body, ctx, node.id, "body")
    ?? (typeof node.body === "string"
      ? React.createElement(
          "span",
          {
            key: `${node.id}-body-text`,
            style: { color: tokenVar("color.text.primary") },
          },
          node.body,
        )
      : null);
  const footer = renderSlot(node.footer, ctx, node.id, "footer");

  const container = React.createElement(
    "section",
    {
      id: node.id,
      role: "region",
      "aria-label": a11y.label,
      "data-flux-component": "FluxCard",
      "data-flux-emphasis": emphasis,
      "data-flux-padding": padding,
      style,
    },
    header ? React.createElement("header", { key: `${node.id}-hdr` }, header) : null,
    body,
    footer ? React.createElement("footer", { key: `${node.id}-ftr` }, footer) : null,
  );
  return asFluxElement(container);
};

export default FluxCard;
