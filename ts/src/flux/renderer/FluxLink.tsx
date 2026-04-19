// flux:scaffold-user
/**
 * FluxLink — inline hyperlink.
 *
 * Invariant: ``href`` and ``action`` are mutually exclusive (XOR). We
 * render an ``<a>`` when ``href`` is present; otherwise a ``<button>``
 * styled like a link (to surface action-driven navigation to assistive
 * tech correctly).
 *
 * Variants: tone (default/muted/danger) × underline (always/hover/never).
 * External links append an external-link icon with ``aria-label="opens in
 * new tab"`` and set ``rel="noopener noreferrer"`` + ``target="_blank"``.
 */

import * as React from "react";
import type { CSSProperties } from "react";
import { asFluxElement, mergeStyles, tokenVar } from "./_shared.js";
import type {
  FluxElement,
  FluxNode,
  FluxRenderContext,
  FluxRenderer,
} from "./types.js";

type Tone = "default" | "muted" | "danger";
type Underline = "always" | "hover" | "never";

const TONE_STYLE: Record<Tone, CSSProperties> = {
  default: {
    color: tokenVar("color.text.link"),
  },
  muted: {
    color: tokenVar("color.text.muted"),
  },
  danger: {
    color: tokenVar("color.text.danger"),
  },
};

const UNDERLINE_STYLE: Record<Underline, CSSProperties> = {
  always: {
    textDecoration: "underline",
    textUnderlineOffset: tokenVar("space.0_5"),
  },
  hover: {
    textDecoration: "none",
    textUnderlineOffset: tokenVar("space.0_5"),
  },
  never: {
    textDecoration: "none",
  },
};

const ExternalIcon: React.FC = () => {
  return React.createElement(
    "svg",
    {
      "aria-label": "opens in new tab",
      role: "img",
      width: 12,
      height: 12,
      viewBox: "0 0 24 24",
      fill: "none",
      stroke: "currentColor",
      strokeWidth: 2,
      style: { marginInlineStart: tokenVar("space.1") },
    },
    React.createElement("path", { d: "M14 3h7v7" }),
    React.createElement("path", { d: "M21 3l-9 9" }),
    React.createElement("path", { d: "M21 14v7H3V3h7" }),
  );
};

const FluxLink: FluxRenderer = (
  node: FluxNode,
  _ctx: FluxRenderContext,
): FluxElement => {
  const tone = (node.tone as Tone) ?? "default";
  const underline = (node.underline as Underline) ?? "hover";
  const label = typeof node.label === "string" ? node.label : "";
  const a11y = (node.accessibility as { label?: string }) ?? {};
  const href = typeof node.href === "string" && node.href.length > 0 ? node.href : undefined;
  const action = typeof node.action === "object" && node.action !== null
    ? node.action
    : undefined;
  const external = Boolean(node.external);

  const style = mergeStyles(
    {
      display: "inline-flex",
      alignItems: "center",
      gap: tokenVar("space.0_5"),
      fontFamily: tokenVar("typography.family.sans"),
      fontWeight: tokenVar("typography.weight.medium"),
      cursor: "pointer",
      background: "none",
      border: "none",
      padding: 0,
      transitionProperty: "color, text-decoration",
      transitionDuration: tokenVar("motion.duration.fast"),
      transitionTimingFunction: tokenVar("motion.easing.standard"),
    },
    TONE_STYLE[tone],
    UNDERLINE_STYLE[underline],
  );

  const children = [
    label,
    external
      ? React.createElement(ExternalIcon, { key: `${node.id}-ext` })
      : null,
  ];

  const dataProps = {
    "data-flux-component": "FluxLink",
    "data-flux-tone": tone,
    "data-flux-underline": underline,
  };

  if (href) {
    const anchor = React.createElement(
      "a",
      {
        id: node.id,
        href,
        style,
        "aria-label": a11y.label ?? label,
        target: external ? "_blank" : undefined,
        rel: external ? "noopener noreferrer" : undefined,
        ...dataProps,
      },
      ...children,
    );
    return asFluxElement(anchor);
  }

  // Action-based link (or XOR violation from malformed input — render as
  // a button styled like a link so screen readers see the correct role).
  const btn = React.createElement(
    "button",
    {
      id: node.id,
      type: "button",
      style,
      "aria-label": a11y.label ?? label,
      "data-flux-action": action ? "true" : undefined,
      ...dataProps,
    },
    ...children,
  );
  return asFluxElement(btn);
};

export default FluxLink;
