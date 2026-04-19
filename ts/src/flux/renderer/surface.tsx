// flux:scaffold-user
/**
 * Public runtime surface for the flux React renderer.
 *
 * ``renderer/index.ts`` and ``renderer/types.ts`` are emitter-owned (W2)
 * and rewritten on every ``just flux`` run, so anything that needs a
 * hand-written signature lives here. Import like:
 *
 *   import { renderFluxSurface, FluxThemeRoot } from "adk-fluent-ts/.../renderer/surface";
 *
 * Exports:
 *   - ``renderFluxSurface(node, ctx)`` — root dispatcher. Walks a surface
 *     tree and calls ``ctx.renderers[node.component]`` or ``ctx.fallback``.
 *   - ``buildFluxRenderContext(...)`` — convenience factory that wires up
 *     the ten renderers, a slot registry, and a naive basic-catalog
 *     fallback.
 *   - ``FluxThemeRoot`` / ``useTheme`` / ``renderTokenPack`` — re-exports
 *     from ``theme.js`` for callers who only want the public surface.
 */

import * as React from "react";
import type { ReactElement } from "react";

import type { FluxElement, FluxNode, FluxRenderContext, FluxRenderer } from "./types.js";

import FluxBadge from "./FluxBadge.js";
import FluxBanner from "./FluxBanner.js";
import FluxButton from "./FluxButton.js";
import FluxCard from "./FluxCard.js";
import FluxLink from "./FluxLink.js";
import FluxMarkdown from "./FluxMarkdown.js";
import FluxProgress from "./FluxProgress.js";
import FluxSkeleton from "./FluxSkeleton.js";
import FluxStack from "./FluxStack.js";
import FluxTextField from "./FluxTextField.js";

export {
  FluxBadge,
  FluxBanner,
  FluxButton,
  FluxCard,
  FluxLink,
  FluxMarkdown,
  FluxProgress,
  FluxSkeleton,
  FluxStack,
  FluxTextField,
};

export { FluxThemeRoot, useTheme, renderTokenPack } from "./theme.js";
export type { TokenPack, FluxThemeRootProps } from "./theme.js";

/** The canonical registry — component name → renderer. */
export const FLUX_RENDERERS: Record<string, FluxRenderer> = {
  FluxBadge,
  FluxBanner,
  FluxButton,
  FluxCard,
  FluxLink,
  FluxMarkdown,
  FluxProgress,
  FluxSkeleton,
  FluxStack,
  FluxTextField,
};

/**
 * A naive fallback renderer that produces plain-text ``<span>`` / ``<div>``
 * elements for basic-catalog component kinds. The visual runner swaps
 * this for a catalog-aware renderer; unit tests rely on the plain output
 * to assert degraded behaviour.
 */
export const defaultFallback = (node: FluxNode): FluxElement => {
  const label =
    typeof node.text === "string"
      ? node.text
      : typeof node.label === "string"
        ? node.label
        : typeof node.source === "string"
          ? node.source
          : "";
  const el = React.createElement(
    "span",
    {
      "data-flux-fallback": node.component,
      "data-flux-node-id": node.id,
    },
    label,
  );
  return el as unknown as FluxElement;
};

export interface BuildContextOptions {
  theme?: Record<string, unknown>;
  catalog?: Record<string, unknown>;
  renderers?: Record<string, FluxRenderer>;
  /** Sidecar map of node id → node, used to resolve slot ids. */
  slots?: Record<string, FluxNode>;
  fallback?: (node: FluxNode) => FluxElement;
}

/** Build a FluxRenderContext with sensible defaults. */
export function buildFluxRenderContext(
  opts: BuildContextOptions = {},
): FluxRenderContext & { slots: Record<string, FluxNode> } {
  return {
    theme: opts.theme ?? {},
    catalog: opts.catalog ?? {},
    renderers: { ...FLUX_RENDERERS, ...(opts.renderers ?? {}) },
    slots: opts.slots ?? {},
    fallback: opts.fallback ?? defaultFallback,
  };
}

/**
 * Walk a surface tree and dispatch to the correct renderer. Unknown
 * component kinds fall through to ``ctx.fallback(node)``. The return
 * value is a ``React.ReactElement`` — callers that only have the
 * generated ``FluxElement`` type can safely narrow via ``as``.
 */
export function renderFluxSurface(node: FluxNode, ctx: FluxRenderContext): ReactElement {
  const renderer = ctx.renderers[node.component];
  if (renderer) {
    return renderer(node, ctx) as unknown as ReactElement;
  }
  return ctx.fallback(node) as unknown as ReactElement;
}
