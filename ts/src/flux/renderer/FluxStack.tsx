// flux:scaffold-user
/**
 * FluxStack — flex-based layout primitive. Variants: direction × gap
 * × align × justify. Children pass through (looked up by id via
 * ctx.slots).
 */

import * as React from "react";
import type { CSSProperties, ReactElement } from "react";
import { asFluxElement, tokenVar } from "./_shared.js";
import type { FluxElement, FluxNode, FluxRenderContext, FluxRenderer } from "./types.js";

type Direction = "vertical" | "horizontal";
type Gap = "1" | "2" | "3" | "4" | "6" | "8";
type Align = "start" | "center" | "end" | "stretch";
type Justify = "start" | "center" | "end" | "between" | "around";

const DIRECTION_MAP: Record<Direction, CSSProperties["flexDirection"]> = {
  vertical: "column",
  horizontal: "row",
};

const ALIGN_MAP: Record<Align, CSSProperties["alignItems"]> = {
  start: "flex-start",
  center: "center",
  end: "flex-end",
  stretch: "stretch",
};

const JUSTIFY_MAP: Record<Justify, CSSProperties["justifyContent"]> = {
  start: "flex-start",
  center: "center",
  end: "flex-end",
  between: "space-between",
  around: "space-around",
};

const FluxStack: FluxRenderer = (node: FluxNode, ctx: FluxRenderContext): FluxElement => {
  const direction = (node.direction as Direction) ?? "vertical";
  const gap = (node.gap as Gap) ?? "3";
  const align = (node.align as Align) ?? "stretch";
  const justify = (node.justify as Justify) ?? "start";
  const wrap = Boolean(node.wrap);
  const a11y = (node.accessibility as { label?: string }) ?? {};
  const childIds = Array.isArray(node.children) ? (node.children as unknown[]) : [];

  const style: CSSProperties = {
    display: "flex",
    flexDirection: DIRECTION_MAP[direction],
    gap: tokenVar(`space.${gap}`),
    alignItems: ALIGN_MAP[align],
    justifyContent: JUSTIFY_MAP[justify],
    flexWrap: wrap ? "wrap" : "nowrap",
  };

  const rendered: Array<ReactElement | null> = [];
  const registry = (ctx as unknown as { slots?: Record<string, FluxNode> }).slots ?? {};
  for (let i = 0; i < childIds.length; i += 1) {
    const id = childIds[i];
    if (typeof id !== "string") continue;
    const child = registry[id];
    if (!child) continue;
    const renderer = ctx.renderers[child.component];
    const el = renderer ? renderer(child, ctx) : ctx.fallback(child);
    rendered.push(
      React.cloneElement(el as unknown as ReactElement, {
        key: `${node.id}-child-${i}`,
      }),
    );
  }

  const container = React.createElement(
    "div",
    {
      id: node.id,
      "aria-label": a11y.label,
      "data-flux-component": "FluxStack",
      "data-flux-direction": direction,
      style,
    },
    ...rendered,
  );
  return asFluxElement(container);
};

export default FluxStack;
