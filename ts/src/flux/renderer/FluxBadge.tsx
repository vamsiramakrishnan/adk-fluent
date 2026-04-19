// flux:scaffold-user
/**
 * FluxBadge — inline label / count / tag.
 *
 * Variants: tone (neutral/primary/success/warning/danger) × variant
 * (subtle/solid) × size (xs/sm/md). compoundVariants lift the ``solid``
 * styling onto ``{primary, success, danger}`` tones.
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

type Tone = "neutral" | "primary" | "success" | "warning" | "danger";
type Variant = "subtle" | "solid";
type Size = "xs" | "sm" | "md";

const TONE_STYLE: Record<Tone, CSSProperties> = {
  neutral: {
    backgroundColor: tokenVar("color.bg.subtle"),
    color: tokenVar("color.text.muted"),
  },
  primary: {
    backgroundColor: tokenVar("color.primary.subtle"),
    color: tokenVar("color.text.primary"),
  },
  success: {
    backgroundColor: tokenVar("color.success.subtle"),
    color: tokenVar("color.success.solid"),
  },
  warning: {
    backgroundColor: tokenVar("color.warning.3"),
    color: tokenVar("color.warning.9"),
  },
  danger: {
    backgroundColor: tokenVar("color.danger.subtle"),
    color: tokenVar("color.danger.solid"),
  },
};

const SIZE_STYLE: Record<Size, CSSProperties> = {
  xs: {
    paddingBlock: tokenVar("space.0_5"),
    paddingInline: tokenVar("space.1"),
    fontSize: tokenVar("typography.size.xs"),
  },
  sm: {
    paddingBlock: tokenVar("space.0_5"),
    paddingInline: tokenVar("space.1_5"),
    fontSize: tokenVar("typography.size.xs"),
  },
  md: {
    paddingBlock: tokenVar("space.1"),
    paddingInline: tokenVar("space.2"),
    fontSize: tokenVar("typography.size.sm"),
  },
};

function compoundSolid(tone: Tone): CSSProperties | undefined {
  switch (tone) {
    case "primary":
      return {
        backgroundColor: tokenVar("color.primary.solid"),
        color: tokenVar("color.text.onBrand"),
      };
    case "success":
      return {
        backgroundColor: tokenVar("color.success.solid"),
        color: tokenVar("color.text.onBrand"),
      };
    case "danger":
      return {
        backgroundColor: tokenVar("color.danger.solid"),
        color: tokenVar("color.text.onBrand"),
      };
    default:
      return undefined;
  }
}

const FluxBadge: FluxRenderer = (
  node: FluxNode,
  _ctx: FluxRenderContext,
): FluxElement => {
  const tone = (node.tone as Tone) ?? "neutral";
  const variant = (node.variant as Variant) ?? "subtle";
  const size = (node.size as Size) ?? "sm";
  const label = typeof node.label === "string" ? node.label : "";
  const a11y = (node.accessibility as { label?: string }) ?? {};

  const base: CSSProperties = {
    display: "inline-flex",
    alignItems: "center",
    fontFamily: tokenVar("typography.family.sans"),
    fontWeight: tokenVar("typography.weight.medium"),
    borderRadius:
      variant === "solid" ? tokenVar("radius.full") : tokenVar("radius.sm"),
    whiteSpace: "nowrap",
  };

  const style = mergeStyles(
    base,
    TONE_STYLE[tone],
    SIZE_STYLE[size],
    variant === "solid" ? compoundSolid(tone) : undefined,
  );

  const span = React.createElement(
    "span",
    {
      id: node.id,
      role: "status",
      "aria-label": a11y.label ?? label,
      "data-flux-component": "FluxBadge",
      "data-flux-tone": tone,
      "data-flux-variant": variant,
      "data-flux-size": size,
      style,
    },
    label,
  );
  return asFluxElement(span);
};

export default FluxBadge;
