/**
 * FluxBanner — inline notification row.
 *
 * A Banner carries a title + message at a specific tone (info / success /
 * warning / danger) and may include an optional call-to-action button
 * and dismiss control. It extends the basic-catalog `Row` because its
 * layout is inherently horizontal: icon on the left, title + message in
 * the middle, action + dismiss on the right.
 *
 * ARIA role hint: renderers should set `role="status"` for info/success
 * (polite) and `role="alert"` for warning/danger (assertive). The actual
 * ARIA dispatch lives in the React renderer (W5); this spec only
 * declares the contract.
 *
 * Budget: `{children: 0, siblings: 3, depth: 4}` — banners are terminal
 * notification nodes; nesting banners inside banners (or stacking more
 * than three on a surface) degrades the signal.
 */

import { defineComponent, z } from "../dsl/types";

export default defineComponent({
  name: "FluxBanner",
  extends: "Row",
  category: "compound",

  // ---------------------------------------------------------------------
  // Schema
  // ---------------------------------------------------------------------
  schema: z.object({
    component: z.literal("FluxBanner"),
    id: z.string(),

    // Content
    title: z.string(),
    message: z.string(),

    // Variant dimensions
    tone: z.enum(["info", "success", "warning", "danger"]).default("info"),

    // Slots by id reference
    icon: z.string().optional(),
    action: z.string().optional(),
    dismiss: z.string().optional(),

    // Accessibility
    accessibility: z
      .object({
        label: z.string(),
        description: z.string().optional(),
      })
      .optional(),
  }),

  // ---------------------------------------------------------------------
  // Slots
  // ---------------------------------------------------------------------
  slots: {
    icon: { kind: "Icon", required: false },
    action: { kind: "FluxButton", required: false, max: 1 },
    dismiss: { kind: "FluxButton", required: false, max: 1 },
  },

  // ---------------------------------------------------------------------
  // Tokens referenced
  // ---------------------------------------------------------------------
  tokens: [
    "color.info.3",
    "color.info.11",
    "color.success.subtle",
    "color.success.solid",
    "color.warning.3",
    "color.warning.9",
    "color.danger.subtle",
    "color.danger.solid",
    "space.2",
    "space.3",
    "space.4",
    "radius.md",
    "shadow.sm",
  ],

  // ---------------------------------------------------------------------
  // Variant recipe (tone-only)
  // ---------------------------------------------------------------------
  variants: {
    tone: {
      info: {
        backgroundColor: "$color.info.3",
        color: "$color.info.11",
        borderRadius: "$radius.md",
        paddingBlock: "$space.3",
        paddingInline: "$space.4",
      },
      success: {
        backgroundColor: "$color.success.subtle",
        color: "$color.success.solid",
        borderRadius: "$radius.md",
        paddingBlock: "$space.3",
        paddingInline: "$space.4",
      },
      warning: {
        backgroundColor: "$color.warning.3",
        color: "$color.warning.9",
        borderRadius: "$radius.md",
        paddingBlock: "$space.3",
        paddingInline: "$space.4",
      },
      danger: {
        backgroundColor: "$color.danger.subtle",
        color: "$color.danger.solid",
        borderRadius: "$radius.md",
        paddingBlock: "$space.3",
        paddingInline: "$space.4",
      },
    },
  },

  // ---------------------------------------------------------------------
  // compoundVariants — danger tone with an action tightens padding.
  // ---------------------------------------------------------------------
  compoundVariants: [
    {
      tone: "danger",
      style: {
        paddingBlock: "$space.2",
        paddingInline: "$space.3",
        boxShadow: "$shadow.sm",
      },
    },
  ],

  defaultVariants: {
    tone: "info",
  },

  // ---------------------------------------------------------------------
  // Accessibility
  // ---------------------------------------------------------------------
  accessibility: {
    label: "optional",
    role: "status",
  },

  // ---------------------------------------------------------------------
  // LLM metadata
  // ---------------------------------------------------------------------
  llm: {
    description:
      "An inline notification row for surface-level messages. Pick tone by urgency: info/success render with role=status (polite); warning/danger render with role=alert (assertive). Attach an optional `action` button for recovery flows and a `dismiss` button for transient messages.",
    tags: ["notification", "status", "alert", "inline"],
    examples: [
      {
        code: `UI.banner("Heads up", "We're updating the pricing page at 5pm UTC.", tone="info")`,
        caption: "Informational banner.",
      },
      {
        code: `UI.banner("Payment failed", "Your card was declined.", tone="danger", action=retry_btn, dismiss=close_btn)`,
        caption: "Danger banner with retry + dismiss controls.",
      },
    ],
    antiPatterns: [
      {
        code: `UI.column([UI.banner(...), UI.banner(...), UI.banner(...), UI.banner(...)])`,
        reason:
          "Stacking more than three banners on one surface drowns the signal. Use a list + counters instead.",
      },
      {
        code: `UI.banner("Saved!", "Your changes were saved.", tone="danger")`,
        reason:
          "tone=danger signals an error. Use tone=success for confirmations.",
      },
    ],
    budget: { children: 0, siblings: 3, depth: 4 },
  },

  // ---------------------------------------------------------------------
  // Renderer mapping
  // ---------------------------------------------------------------------
  renderer: {
    react: "./renderers/react/FluxBanner.tsx",
    fallback: {
      component: "Row",
      map: {
        title: "child",
        message: "child",
      },
      notes:
        "Basic renderers drop tone + role + icon slot; the row stays but reads as plain text with no urgency affordance.",
    },
  },
});
