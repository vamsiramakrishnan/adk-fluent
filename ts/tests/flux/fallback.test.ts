/**
 * W5 — basic-catalog fallback smoke test.
 *
 * Instantiates a ``FluxRenderContext`` with an empty ``renderers`` map and
 * a naive ``BasicText`` fallback, then asserts that feeding a FluxMarkdown
 * node through ``renderFluxSurface`` degrades to readable plain text.
 *
 * This is the contract described in ARCHITECTURE §10 — every flux
 * component ships a degrade path; the fallback renderer is how renderers
 * that only speak basic-catalog survive. The test protects against
 * regressions where a renderer mutates ``node.component`` or short-
 * circuits the fallback lookup.
 */
import { describe, expect, it } from "vitest";
import * as React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import type { FluxElement, FluxNode, FluxRenderContext } from "../../src/flux/renderer/types.js";
import { renderFluxSurface } from "../../src/flux/renderer/surface.js";

function BasicText(props: { text: string }): React.ReactElement {
  return React.createElement(
    "span",
    { "data-basic": "Text", "data-kind": "BasicText" },
    props.text,
  );
}

describe("renderFluxSurface — fallback path", () => {
  it("degrades unknown components to the caller's fallback component", () => {
    const ctx: FluxRenderContext = {
      theme: {},
      catalog: {},
      renderers: {},
      fallback: (node: FluxNode): FluxElement => {
        const text =
          typeof node.source === "string"
            ? node.source
            : typeof node.label === "string"
              ? node.label
              : "";
        return React.createElement(BasicText, { text }) as unknown as FluxElement;
      },
    };

    const markdownNode: FluxNode = {
      component: "FluxMarkdown",
      id: "md-1",
      source: "**Hello**, world!",
      size: "md",
      proseStyle: "default",
    };

    const element = renderFluxSurface(markdownNode, ctx);
    const html = renderToStaticMarkup(element);

    // The fallback was invoked (BasicText marker present).
    expect(html).toContain('data-kind="BasicText"');
    expect(html).toContain('data-basic="Text"');
    // The source text is preserved verbatim — degraded but readable.
    expect(html).toContain("**Hello**, world!");
  });

  it("dispatches to a registered renderer when one is available", () => {
    // Registered renderer — the identity map should route to it.
    const ctx: FluxRenderContext = {
      theme: {},
      catalog: {},
      renderers: {
        FluxBadge: ((node: FluxNode) =>
          React.createElement(
            "span",
            { "data-flux-registered": "FluxBadge" },
            typeof node.label === "string" ? node.label : "",
          ) as unknown as FluxElement) as FluxRenderContext["renderers"][string],
      },
      fallback: (node: FluxNode): FluxElement =>
        React.createElement("span", {}, node.component) as unknown as FluxElement,
    };

    const node: FluxNode = {
      component: "FluxBadge",
      id: "badge-1",
      label: "New",
      tone: "primary",
      variant: "solid",
      size: "sm",
    };
    const html = renderToStaticMarkup(renderFluxSurface(node, ctx));
    expect(html).toContain('data-flux-registered="FluxBadge"');
    expect(html).toContain("New");
  });
});
