// flux:scaffold-user
/**
 * FluxSkeleton — loading-state placeholder.
 *
 * shape × size drives the geometry; circle sizes pin width == height
 * per the compoundVariants. ``count`` repeats the placeholder. Shimmer
 * animation uses ``motion.duration.slow`` + ``motion.easing.emphasized``.
 * Presentational only — always ``aria-hidden="true"``.
 */

import * as React from "react";
import type { CSSProperties } from "react";
import { asFluxElement, tokenVar } from "./_shared.js";
import type {
  FluxElement,
  FluxNode,
  FluxRenderContext,
  FluxRenderer,
} from "./types.js";

type Shape = "text" | "circle" | "rect";
type Size = "xs" | "sm" | "md" | "lg" | "xl";

const SIZE_HEIGHT: Record<Size, string> = {
  xs: tokenVar("space.2"),
  sm: tokenVar("space.3"),
  md: tokenVar("space.4"),
  lg: tokenVar("space.6"),
  xl: tokenVar("space.12"),
};

const CIRCLE_DIM: Partial<Record<Size, string>> = {
  md: tokenVar("space.5"),
  lg: tokenVar("space.8"),
  xl: tokenVar("space.12"),
};

const SHIMMER_KEYFRAMES = `
@keyframes flux-skeleton-shimmer {
  0% { background-position: -200% 0; }
  100% { background-position: 200% 0; }
}
`;

function radius(shape: Shape): string {
  switch (shape) {
    case "text":
      return tokenVar("radius.sm");
    case "circle":
      return tokenVar("radius.full");
    case "rect":
      return tokenVar("radius.md");
  }
}

const FluxSkeleton: FluxRenderer = (
  node: FluxNode,
  _ctx: FluxRenderContext,
): FluxElement => {
  const shape = (node.shape as Shape) ?? "text";
  const size = (node.size as Size) ?? "md";
  const count = typeof node.count === "number" && node.count > 0
    ? Math.floor(node.count)
    : 1;
  const widthOverride = typeof node.width === "string" ? node.width : undefined;
  const heightOverride = typeof node.height === "string" ? node.height : undefined;

  const circleDim = shape === "circle" ? CIRCLE_DIM[size] : undefined;

  const base: CSSProperties = {
    display: "block",
    borderRadius: radius(shape),
    backgroundColor: tokenVar("color.bg.subtle"),
    backgroundImage:
      "linear-gradient(90deg, transparent 0%, rgba(255,255,255,0.18) 50%, transparent 100%)",
    backgroundSize: "200% 100%",
    animationName: "flux-skeleton-shimmer",
    animationDuration: tokenVar("motion.duration.slow"),
    animationTimingFunction: tokenVar("motion.easing.emphasized"),
    animationIterationCount: "infinite",
    height: heightOverride ?? circleDim ?? SIZE_HEIGHT[size],
    width:
      widthOverride
      ?? circleDim
      ?? (shape === "text" ? "100%" : shape === "rect" ? "100%" : undefined),
  };

  const items: React.ReactElement[] = [];
  for (let i = 0; i < count; i += 1) {
    items.push(
      React.createElement("span", {
        key: `${node.id}-${i}`,
        style: {
          ...base,
          width:
            shape === "text" && i === count - 1 && count > 1
              ? "70%"
              : base.width,
        },
      }),
    );
  }

  const container = React.createElement(
    "div",
    {
      id: node.id,
      "aria-hidden": "true",
      role: "presentation",
      "data-flux-component": "FluxSkeleton",
      "data-flux-shape": shape,
      "data-flux-size": size,
      style: {
        display: "flex",
        flexDirection: "column",
        gap: tokenVar("space.2"),
      },
    },
    React.createElement("style", { "data-flux-keyframes": "skeleton" }, SHIMMER_KEYFRAMES),
    ...items,
  );
  return asFluxElement(container);
};

export default FluxSkeleton;
