// flux:scaffold-user
/**
 * FluxProgress — progress indicator.
 *
 *   determinate=true  → native ``<progress value={v} max={100}>`` so
 *                       assistive tech gets a proper progressbar role
 *                       with current/min/max values.
 *   determinate=false → a themed track + shimmering fill. Shimmer uses
 *                       ``motion.duration.slow`` and ``motion.easing.emphasized``
 *                       tokens via a keyframe declared in a scoped ``<style>``.
 *
 * ``aria-valuenow`` is set in both modes (max clamp for indeterminate).
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

type Tone = "default" | "success" | "warning" | "danger";
type Size = "sm" | "md" | "lg";

const TONE_FILL: Record<Tone, string> = {
  default: tokenVar("color.primary.solid"),
  success: tokenVar("color.success.solid"),
  warning: tokenVar("color.warning.7"),
  danger: tokenVar("color.danger.solid"),
};

const SIZE_HEIGHT: Record<Size, string> = {
  sm: tokenVar("space.1"),
  md: tokenVar("space.1_5"),
  lg: tokenVar("space.2"),
};

const SHIMMER_KEYFRAMES = `
@keyframes flux-progress-shimmer {
  0% { transform: translateX(-100%); }
  100% { transform: translateX(250%); }
}
@keyframes flux-spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}
`;

const FluxProgress: FluxRenderer = (
  node: FluxNode,
  _ctx: FluxRenderContext,
): FluxElement => {
  const tone = (node.tone as Tone) ?? "default";
  const size = (node.size as Size) ?? "md";
  const determinate = node.determinate !== false; // default true
  const rawValue = typeof node.value === "number" ? node.value : 0;
  const value = Math.max(0, Math.min(100, rawValue));
  const a11y = (node.accessibility as { label?: string }) ?? {};
  const label = typeof node.label === "string" ? node.label : a11y.label ?? "Progress";

  const height = SIZE_HEIGHT[size];
  const fill = TONE_FILL[tone];

  const trackStyle: CSSProperties = {
    position: "relative",
    width: "100%",
    height,
    backgroundColor: tokenVar("color.bg.subtle"),
    borderRadius: tokenVar("radius.full"),
    overflow: "hidden",
  };

  const containerStyle: CSSProperties = {
    display: "flex",
    flexDirection: "column",
    gap: tokenVar("space.1"),
    fontFamily: tokenVar("typography.family.sans"),
  };

  const labelEl = React.createElement(
    "span",
    {
      style: {
        fontSize: tokenVar("typography.size.sm"),
        color: tokenVar("color.text.muted"),
      },
    },
    label,
  );

  if (determinate) {
    const bar = React.createElement(
      "progress",
      {
        id: node.id,
        value,
        max: 100,
        "aria-label": a11y.label ?? label,
        "aria-valuenow": value,
        "aria-valuemin": 0,
        "aria-valuemax": 100,
        "data-flux-component": "FluxProgress",
        "data-flux-tone": tone,
        "data-flux-size": size,
        "data-flux-determinate": "true",
        style: {
          width: "100%",
          height,
          appearance: "none",
          border: "none",
          backgroundColor: tokenVar("color.bg.subtle"),
          color: fill, // Firefox uses color for -moz-progress-bar
          borderRadius: tokenVar("radius.full"),
          overflow: "hidden",
          // Modern browsers: style the filled portion via pseudo-elements.
          // We inject a small <style> tag for cross-browser coverage.
        },
      },
      `${value}%`,
    );
    const injected = React.createElement(
      "style",
      { "data-flux-keyframes": "progress" },
      `${SHIMMER_KEYFRAMES}
#${node.id}::-webkit-progress-bar { background-color: ${tokenVar("color.bg.subtle")}; border-radius: ${tokenVar("radius.full")}; }
#${node.id}::-webkit-progress-value { background-color: ${fill}; border-radius: ${tokenVar("radius.full")}; }
#${node.id}::-moz-progress-bar { background-color: ${fill}; border-radius: ${tokenVar("radius.full")}; }
`,
    );
    const wrapper = React.createElement(
      "div",
      { style: containerStyle },
      labelEl,
      injected,
      bar,
    );
    return asFluxElement(wrapper);
  }

  const shimmerFill: CSSProperties = {
    position: "absolute",
    inset: 0,
    backgroundImage: `linear-gradient(90deg, transparent, ${fill}, transparent)`,
    animationName: "flux-progress-shimmer",
    animationDuration: tokenVar("motion.duration.slow"),
    animationTimingFunction: tokenVar("motion.easing.emphasized"),
    animationIterationCount: "infinite",
  };

  const track = React.createElement(
    "div",
    {
      id: node.id,
      role: "progressbar",
      "aria-label": a11y.label ?? label,
      "aria-valuenow": 0,
      "aria-valuemin": 0,
      "aria-valuemax": 100,
      "data-flux-component": "FluxProgress",
      "data-flux-tone": tone,
      "data-flux-size": size,
      "data-flux-determinate": "false",
      style: trackStyle,
    },
    React.createElement("style", { "data-flux-keyframes": "progress" }, SHIMMER_KEYFRAMES),
    React.createElement("div", { style: shimmerFill }),
  );

  const wrapper = React.createElement(
    "div",
    { style: containerStyle },
    labelEl,
    track,
  );
  return asFluxElement(wrapper);
};

export default FluxProgress;
