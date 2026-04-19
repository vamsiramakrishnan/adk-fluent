// flux:scaffold-user
/**
 * FluxButton — clickable action primitive.
 *
 * Variants: tone × size × emphasis, plus compoundVariants for
 * ``tone=danger + emphasis=outline`` (danger border + text), ``tone=primary
 * + emphasis=soft`` (soft primary), and ``tone=neutral + emphasis=ghost``
 * (muted ghost).
 *
 * Slots: leadingIcon / trailingIcon looked up by id from ctx.slots.
 *
 * Accessibility: label is required (enforced by DSL); we set ``aria-label``
 * from ``accessibility.label`` and propagate ``aria-busy`` when loading.
 */

import * as React from "react";
import type { CSSProperties } from "react";
import { asFluxElement, mergeStyles, renderSlot, tokenVar } from "./_shared.js";
import type { FluxElement, FluxNode, FluxRenderContext, FluxRenderer } from "./types.js";

type Tone = "neutral" | "primary" | "danger" | "success";
type Size = "sm" | "md" | "lg";
type Emphasis = "solid" | "soft" | "outline" | "ghost";

const TONE_BASE: Record<Tone, CSSProperties> = {
  neutral: {
    backgroundColor: tokenVar("color.bg.subtle"),
    color: tokenVar("color.text.primary"),
    borderColor: tokenVar("color.border.default"),
  },
  primary: {
    backgroundColor: tokenVar("color.primary.solid"),
    color: tokenVar("color.text.onBrand"),
    borderColor: tokenVar("color.primary.solid"),
  },
  danger: {
    backgroundColor: tokenVar("color.danger.solid"),
    color: tokenVar("color.text.onBrand"),
    borderColor: tokenVar("color.danger.solid"),
  },
  success: {
    backgroundColor: tokenVar("color.success.solid"),
    color: tokenVar("color.text.onBrand"),
    borderColor: tokenVar("color.success.solid"),
  },
};

const SIZE_STYLE: Record<Size, CSSProperties> = {
  sm: {
    paddingBlock: tokenVar("space.2"),
    paddingInline: tokenVar("space.3"),
    fontSize: tokenVar("typography.size.sm"),
    borderRadius: tokenVar("radius.md"),
  },
  md: {
    paddingBlock: tokenVar("space.2"),
    paddingInline: tokenVar("space.4"),
    fontSize: tokenVar("typography.size.md"),
    borderRadius: tokenVar("radius.md"),
  },
  lg: {
    paddingBlock: tokenVar("space.3"),
    paddingInline: tokenVar("space.4"),
    fontSize: tokenVar("typography.size.lg"),
    borderRadius: tokenVar("radius.lg"),
  },
};

const EMPHASIS_STYLE: Record<Emphasis, CSSProperties> = {
  solid: {
    borderWidth: "0px",
    borderStyle: "solid",
    boxShadow: tokenVar("shadow.sm"),
  },
  soft: {
    backgroundColor: tokenVar("color.primary.subtle"),
    color: tokenVar("color.text.primary"),
    borderWidth: "0px",
    borderStyle: "solid",
  },
  outline: {
    backgroundColor: "transparent",
    borderWidth: "1px",
    borderStyle: "solid",
    color: tokenVar("color.text.primary"),
  },
  ghost: {
    backgroundColor: "transparent",
    borderWidth: "0px",
    borderStyle: "solid",
    color: tokenVar("color.text.primary"),
  },
};

function compoundStyle(tone: Tone, emphasis: Emphasis): CSSProperties | undefined {
  if (tone === "danger" && emphasis === "outline") {
    return {
      borderColor: tokenVar("color.danger.solid"),
      color: tokenVar("color.text.danger"),
    };
  }
  if (tone === "primary" && emphasis === "soft") {
    return {
      backgroundColor: tokenVar("color.primary.subtle"),
      color: tokenVar("color.text.primary"),
    };
  }
  if (tone === "neutral" && emphasis === "ghost") {
    return { color: tokenVar("color.text.muted") };
  }
  return undefined;
}

const Spinner: React.FC<{ size: number }> = ({ size }) => {
  return React.createElement("span", {
    "aria-hidden": "true",
    style: {
      display: "inline-block",
      width: size,
      height: size,
      border: "2px solid currentColor",
      borderTopColor: "transparent",
      borderRadius: "50%",
      animation: "flux-spin 0.8s linear infinite",
      marginInlineEnd: tokenVar("space.2"),
    },
  });
};

const FluxButton: FluxRenderer = (node: FluxNode, ctx: FluxRenderContext): FluxElement => {
  const tone = (node.tone as Tone) ?? "neutral";
  const size = (node.size as Size) ?? "md";
  const emphasis = (node.emphasis as Emphasis) ?? "solid";
  const label = typeof node.label === "string" ? node.label : "";
  const disabled = Boolean(node.disabled);
  const loading = Boolean(node.loading);
  const a11y = (node.accessibility as { label?: string }) ?? {};

  const style = mergeStyles(
    {
      display: "inline-flex",
      alignItems: "center",
      justifyContent: "center",
      gap: tokenVar("space.2"),
      cursor: disabled || loading ? "not-allowed" : "pointer",
      fontWeight: tokenVar("typography.weight.medium"),
      fontFamily: tokenVar("typography.family.sans"),
      transitionProperty: "background-color, color, box-shadow, border-color",
      transitionDuration: tokenVar("motion.duration.fast"),
      transitionTimingFunction: tokenVar("motion.easing.standard"),
      pointerEvents: disabled || loading ? "none" : "auto",
      opacity: disabled ? 0.55 : 1,
    },
    TONE_BASE[tone],
    SIZE_STYLE[size],
    EMPHASIS_STYLE[emphasis],
    compoundStyle(tone, emphasis),
  );

  const leading = renderSlot(node.leadingIcon, ctx, node.id, "leading");
  const trailing = renderSlot(node.trailingIcon, ctx, node.id, "trailing");

  const spinnerSize = size === "lg" ? 16 : size === "md" ? 14 : 12;

  const element = React.createElement(
    "button",
    {
      type: "button",
      id: node.id,
      disabled,
      "aria-label": a11y.label ?? label,
      "aria-busy": loading || undefined,
      "data-flux-component": "FluxButton",
      "data-flux-tone": tone,
      "data-flux-size": size,
      "data-flux-emphasis": emphasis,
      style,
      onFocus: (event: React.FocusEvent<HTMLButtonElement>) => {
        event.currentTarget.style.boxShadow = tokenVar("shadow.focus");
        event.currentTarget.style.borderColor = tokenVar("color.border.focus");
      },
      onBlur: (event: React.FocusEvent<HTMLButtonElement>) => {
        event.currentTarget.style.boxShadow = String(style.boxShadow ?? "");
        event.currentTarget.style.borderColor = String(style.borderColor ?? "");
      },
    },
    loading ? React.createElement(Spinner, { size: spinnerSize }) : leading,
    React.createElement("span", { style: { whiteSpace: "nowrap" } }, label),
    loading ? null : trailing,
  );

  return asFluxElement(element);
};

export default FluxButton;
