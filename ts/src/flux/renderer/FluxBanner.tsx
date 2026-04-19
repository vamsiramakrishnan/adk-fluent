// flux:scaffold-user
/**
 * FluxBanner — inline notification row.
 *
 * Tone drives both styling and ARIA role:
 *   info / success → role="status" (polite)
 *   warning / danger → role="alert" (assertive)
 *
 * Slots: action (FluxButton) and dismiss (FluxButton), each optional and
 * looked up by id from ctx.slots.
 */

import * as React from "react";
import type { CSSProperties } from "react";
import { asFluxElement, mergeStyles, renderSlot, tokenVar } from "./_shared.js";
import type { FluxElement, FluxNode, FluxRenderContext, FluxRenderer } from "./types.js";

type Tone = "info" | "success" | "warning" | "danger";

const TONE_STYLE: Record<Tone, CSSProperties> = {
  info: {
    backgroundColor: tokenVar("color.info.3"),
    color: tokenVar("color.info.11"),
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

const TONE_ROLE: Record<Tone, "status" | "alert"> = {
  info: "status",
  success: "status",
  warning: "alert",
  danger: "alert",
};

const FluxBanner: FluxRenderer = (node: FluxNode, ctx: FluxRenderContext): FluxElement => {
  const tone = (node.tone as Tone) ?? "info";
  const title = typeof node.title === "string" ? node.title : "";
  const message = typeof node.message === "string" ? node.message : "";
  const role = TONE_ROLE[tone];
  const a11y = (node.accessibility as { label?: string }) ?? {};

  const style = mergeStyles(
    {
      display: "flex",
      alignItems: "flex-start",
      gap: tokenVar("space.3"),
      paddingBlock: tone === "danger" ? tokenVar("space.2") : tokenVar("space.3"),
      paddingInline: tone === "danger" ? tokenVar("space.3") : tokenVar("space.4"),
      borderRadius: tokenVar("radius.md"),
      boxShadow: tone === "danger" ? tokenVar("shadow.sm") : "none",
      fontFamily: tokenVar("typography.family.sans"),
    },
    TONE_STYLE[tone],
  );

  const action = renderSlot(node.action, ctx, node.id, "action");
  const dismiss = renderSlot(node.dismiss, ctx, node.id, "dismiss");

  const body = React.createElement(
    "div",
    { style: { flex: 1, display: "flex", flexDirection: "column", gap: tokenVar("space.1") } },
    React.createElement(
      "strong",
      {
        style: {
          fontSize: tokenVar("typography.size.md"),
          fontWeight: tokenVar("typography.weight.semibold"),
        },
      },
      title,
    ),
    React.createElement(
      "span",
      {
        style: {
          fontSize: tokenVar("typography.size.sm"),
          lineHeight: tokenVar("typography.lineHeight.normal"),
        },
      },
      message,
    ),
  );

  const container = React.createElement(
    "div",
    {
      id: node.id,
      role,
      "aria-label": a11y.label ?? title,
      "data-flux-component": "FluxBanner",
      "data-flux-tone": tone,
      style,
    },
    body,
    action ? React.createElement("div", { key: `${node.id}-action` }, action) : null,
    dismiss ? React.createElement("div", { key: `${node.id}-dismiss` }, dismiss) : null,
  );

  return asFluxElement(container);
};

export default FluxBanner;
