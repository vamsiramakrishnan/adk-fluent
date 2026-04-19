/**
 * FluxLink — inline hyperlink or action-trigger.
 *
 * Every link is either a navigation (`href`) *or* an action dispatch
 * (`action`). The Zod refinement below enforces XOR: both-set and
 * both-empty are rejected at load time, so the LLM can't emit an
 * ambiguous link. `tone` carries semantic colour; `underline` controls
 * the typography underline rule; `external` renders the outbound-link
 * glyph and sets `rel="noopener noreferrer"` in the renderer.
 *
 * Accessibility: a link with a visible text label is self-described, so
 * `accessibility.label` is optional. Authors should still provide one
 * when the label is non-textual (e.g. an icon-only link).
 */

import { defineComponent, z } from "../dsl/types";

export default defineComponent({
  name: "FluxLink",
  extends: "Text",
  category: "primitive",

  // ---------------------------------------------------------------------
  // Schema — XOR invariant enforced via .refine()
  // ---------------------------------------------------------------------
  schema: z
    .object({
      component: z.literal("FluxLink"),
      id: z.string(),

      // Content
      label: z.string(),

      // Destination: exactly one of href / action
      href: z.string().optional(),
      action: z
        .object({
          event: z.object({
            name: z.string(),
            context: z.record(z.string(), z.unknown()).optional(),
          }),
        })
        .optional(),

      // Variant dimensions
      tone: z.enum(["default", "muted", "danger"]).default("default"),
      underline: z.enum(["always", "hover", "never"]).default("hover"),

      // Behavior
      external: z.boolean().optional(),

      // Accessibility (optional — visible label usually suffices).
      accessibility: z
        .object({
          label: z.string(),
          description: z.string().optional(),
        })
        .optional(),
    })
    .refine(
      (data) => {
        const hasHref =
          typeof data.href === "string" && data.href.trim().length > 0;
        const hasAction = data.action !== undefined;
        return hasHref !== hasAction; // strict XOR
      },
      {
        message:
          "FluxLink requires exactly one of `href` or `action` (not both, not neither).",
      },
    ),

  // ---------------------------------------------------------------------
  // Tokens referenced
  // ---------------------------------------------------------------------
  tokens: [
    "color.text.link",
    "color.text.muted",
    "color.text.danger",
    "color.primary.solidHover",
    "color.danger.solidHover",
    "space.0_5",
    "typography.weight.medium",
    "motion.duration.fast",
    "motion.easing.standard",
  ],

  // ---------------------------------------------------------------------
  // Variant recipe (tone x underline)
  // ---------------------------------------------------------------------
  variants: {
    tone: {
      default: {
        color: "$color.text.link",
        hoverColor: "$color.primary.solidHover",
        fontWeight: "$typography.weight.medium",
      },
      muted: {
        color: "$color.text.muted",
        hoverColor: "$color.text.link",
        fontWeight: "$typography.weight.medium",
      },
      danger: {
        color: "$color.text.danger",
        hoverColor: "$color.danger.solidHover",
        fontWeight: "$typography.weight.medium",
      },
    },
    underline: {
      always: {
        textDecoration: "underline",
        textUnderlineOffset: "$space.0_5",
      },
      hover: {
        textDecoration: "none",
        textUnderlineOffset: "$space.0_5",
      },
      never: {
        textDecoration: "none",
      },
    },
  },

  // ---------------------------------------------------------------------
  // compoundVariants — external + underline=hover needs icon spacing.
  // ---------------------------------------------------------------------
  compoundVariants: [
    {
      underline: "hover",
      style: {
        transitionDuration: "$motion.duration.fast",
        transitionTimingFunction: "$motion.easing.standard",
      },
    },
  ],

  defaultVariants: {
    tone: "default",
    underline: "hover",
  },

  // ---------------------------------------------------------------------
  // Accessibility
  // ---------------------------------------------------------------------
  accessibility: {
    label: "optional",
    role: "link",
    keyboard: [
      { key: "Enter", action: "activate" },
    ],
  },

  // ---------------------------------------------------------------------
  // LLM metadata
  // ---------------------------------------------------------------------
  llm: {
    description:
      "An inline hyperlink. Set `href` for navigation *or* `action` for an auth-gated / custom dispatch — never both. Use `external=True` for off-surface URLs so the renderer adds the external-link affordance and `rel=noopener`.",
    tags: ["navigation", "inline", "link"],
    examples: [
      {
        code: `UI.link("Pricing", href="/pricing")`,
        caption: "Internal navigation.",
      },
      {
        code: `UI.link("Read the docs", href="https://docs.example.com", external=True)`,
        caption: "External link with external-icon affordance.",
      },
      {
        code: `UI.link("Sign in to continue", action="open_auth_modal", tone="default")`,
        caption: "Action-based link that triggers a server event instead of navigating.",
      },
    ],
    antiPatterns: [
      {
        code: `UI.link("Buy", href="/checkout", action="buy")`,
        reason:
          "A link has exactly one destination. Pick either `href` (navigate) or `action` (dispatch).",
      },
      {
        code: `UI.link("Click here", href="")`,
        reason:
          "Empty `href` renders a broken anchor. Use `action` when there is no URL.",
      },
    ],
    budget: { children: 0, siblings: 12, depth: 6 },
  },

  // ---------------------------------------------------------------------
  // Renderer mapping
  // ---------------------------------------------------------------------
  renderer: {
    react: "./renderers/react/FluxLink.tsx",
    fallback: {
      component: "Text",
      map: {
        label: "text",
      },
      notes:
        "Basic catalog has no Link component; renderers degrade to inline Text with the label visible and the destination lost. The fluent guard warns when a FluxLink falls back to basic.",
    },
  },
});
