// flux:scaffold-user
/**
 * FluxTextField — single-line text input.
 *
 * Variants: size (sm/md/lg) × state (default/error/success/warning).
 * Slots: leadingIcon, trailingIcon, helper (all optional).
 * Accessibility: ``label`` is required (DSL invariant). We map it to
 * ``aria-label``; helper text and error text are associated via
 * ``aria-describedby`` / ``aria-errormessage``.
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

type Size = "sm" | "md" | "lg";
type State = "default" | "error" | "success" | "warning";

const SIZE_STYLE: Record<Size, CSSProperties> = {
  sm: {
    paddingBlock: tokenVar("space.2"),
    paddingInline: tokenVar("space.3"),
    fontSize: tokenVar("typography.size.sm"),
    borderRadius: tokenVar("radius.md"),
  },
  md: {
    paddingBlock: tokenVar("space.2"),
    paddingInline: tokenVar("space.3"),
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

const STATE_STYLE: Record<State, CSSProperties> = {
  default: {
    backgroundColor: tokenVar("color.bg.surface"),
    borderColor: tokenVar("color.border.default"),
    color: tokenVar("color.text.primary"),
  },
  error: {
    backgroundColor: tokenVar("color.bg.surface"),
    borderColor: tokenVar("color.border.danger"),
    color: tokenVar("color.text.primary"),
  },
  success: {
    backgroundColor: tokenVar("color.bg.surface"),
    borderColor: tokenVar("color.success.solid"),
    color: tokenVar("color.text.primary"),
  },
  warning: {
    backgroundColor: tokenVar("color.bg.surface"),
    borderColor: tokenVar("color.warning.7"),
    color: tokenVar("color.text.primary"),
  },
};

const FluxTextField: FluxRenderer = (
  node: FluxNode,
  ctx: FluxRenderContext,
): FluxElement => {
  const size = (node.size as Size) ?? "md";
  const state = (node.state as State) ?? "default";
  const a11y = (node.accessibility as { label?: string; description?: string }) ?? {};
  const label = a11y.label ?? "input";
  const helperId = `${node.id}-helper`;
  const errorId = `${node.id}-error`;

  const inputStyle = mergeStyles(
    {
      width: "100%",
      borderWidth: "1px",
      borderStyle: "solid",
      fontFamily: tokenVar("typography.family.sans"),
      outline: "none",
      transitionProperty: "border-color, box-shadow",
      transitionDuration: tokenVar("motion.duration.fast"),
      transitionTimingFunction: tokenVar("motion.easing.standard"),
    },
    SIZE_STYLE[size],
    STATE_STYLE[state],
    // compound state=error + size=lg
    state === "error" && size === "lg"
      ? { color: tokenVar("color.text.danger"), fontSize: tokenVar("typography.size.lg") }
      : undefined,
  );

  const wrapperStyle: CSSProperties = {
    display: "flex",
    flexDirection: "column",
    gap: tokenVar("space.1_5"),
    fontFamily: tokenVar("typography.family.sans"),
  };

  const leading = renderSlot(node.leadingIcon, ctx, node.id, "leading");
  const trailing = renderSlot(node.trailingIcon, ctx, node.id, "trailing");
  const helperSlot = renderSlot(node.helper as unknown, ctx, node.id, "helper");

  const ariaProps: Record<string, unknown> = {
    "aria-label": label,
    "data-flux-component": "FluxTextField",
    "data-flux-state": state,
    "data-flux-size": size,
  };
  if (a11y.description) ariaProps["aria-describedby"] = helperId;
  if (state === "error" && typeof node.error === "string") {
    ariaProps["aria-invalid"] = "true";
    ariaProps["aria-errormessage"] = errorId;
  }

  const input = React.createElement("input", {
    id: node.id,
    type: (node.type as string) ?? "text",
    value: typeof node.value === "string" ? node.value : undefined,
    placeholder: typeof node.placeholder === "string" ? node.placeholder : undefined,
    disabled: Boolean(node.disabled) || undefined,
    readOnly: Boolean(node.readonly) || undefined,
    required: Boolean(node.required) || undefined,
    maxLength: typeof node.maxLength === "number" ? node.maxLength : undefined,
    style: inputStyle,
    readonly: undefined,
    ...ariaProps,
    onChange: () => {
      // Controlled upstream; no-op for rendering-only surfaces.
    },
  });

  const inputRow = React.createElement(
    "span",
    {
      style: {
        display: "inline-flex",
        alignItems: "center",
        gap: tokenVar("space.2"),
        width: "100%",
      },
    },
    leading,
    input,
    trailing,
  );

  const helper =
    helperSlot
    ?? (typeof node.helper === "string" && node.helper.length > 0
      ? React.createElement(
          "span",
          {
            id: helperId,
            style: {
              color: tokenVar("color.text.muted"),
              fontSize: tokenVar("typography.size.sm"),
            },
          },
          node.helper,
        )
      : null);

  const errorEl =
    state === "error" && typeof node.error === "string" && node.error.length > 0
      ? React.createElement(
          "span",
          {
            id: errorId,
            role: "alert",
            style: {
              color: tokenVar("color.text.danger"),
              fontSize: tokenVar("typography.size.sm"),
            },
          },
          node.error,
        )
      : null;

  const wrapper = React.createElement(
    "label",
    { style: wrapperStyle, htmlFor: node.id },
    React.createElement(
      "span",
      {
        style: {
          fontSize: tokenVar("typography.size.sm"),
          fontWeight: tokenVar("typography.weight.medium"),
          color: tokenVar("color.text.primary"),
        },
      },
      label,
    ),
    inputRow,
    helper,
    errorEl,
  );

  return asFluxElement(wrapper);
};

export default FluxTextField;
