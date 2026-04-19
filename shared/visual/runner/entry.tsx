// flux:scaffold-user
/**
 * Test harness entry for the Playwright visual runner.
 *
 * Loaded by ``runner.ts`` which bundles this file with esbuild and
 * injects the result into a minimal HTML shell. The shell writes a JSON
 * fixture plus a theme pack id onto ``window`` before the bundle boots;
 * the bundle reads both, renders the surface into ``#flux-root`` under
 * ``<FluxThemeRoot>``, and signals readiness via ``window.__FLUX_READY__``.
 */

import * as React from "react";
import { createRoot } from "react-dom/client";

import {
  FLUX_RENDERERS,
  FluxThemeRoot,
  buildFluxRenderContext,
  renderFluxSurface,
} from "../../../ts/src/flux/renderer/surface.js";

type SurfaceFixture = {
  name: string;
  description?: string;
  node: { component: string; id: string; [k: string]: unknown };
  slots?: Record<string, { component: string; id: string; [k: string]: unknown }>;
};

declare global {
  interface Window {
    __FLUX_FIXTURE__: SurfaceFixture;
    __FLUX_THEME_ID__: string;
    __FLUX_THEME_PACK__: Record<string, unknown>;
    __FLUX_READY__?: boolean;
  }
}

function boot() {
  const fixture = window.__FLUX_FIXTURE__;
  const themeId = window.__FLUX_THEME_ID__;
  const pack = window.__FLUX_THEME_PACK__;

  const slots = (fixture.slots ?? {}) as Parameters<
    typeof buildFluxRenderContext
  >[0] extends { slots?: infer S } ? NonNullable<S> : never;

  const ctx = buildFluxRenderContext({
    theme: pack,
    renderers: FLUX_RENDERERS,
    slots,
  });

  const mount = document.getElementById("flux-root");
  if (!mount) throw new Error("missing #flux-root");

  const root = createRoot(mount);
  root.render(
    React.createElement(
      FluxThemeRoot,
      { packId: themeId, pack, className: "flux-harness" },
      React.createElement(
        "div",
        {
          style: {
            padding: "24px",
            minWidth: "320px",
            minHeight: "80px",
            boxSizing: "border-box",
          },
        },
        renderFluxSurface(fixture.node, ctx),
      ),
    ),
  );

  // Signal the test when the first paint completes so screenshots don't
  // race an in-flight animation (indeterminate progress / skeleton).
  requestAnimationFrame(() => {
    window.__FLUX_READY__ = true;
  });
}

boot();
