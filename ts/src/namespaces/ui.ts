/**
 * UI — Agent-to-UI composition namespace (A2UI).
 *
 * Declarative UI composition for agents.
 * Compose with .row() (horizontal) or .column() (vertical).
 *
 * Usage:
 *   agent.ui(UI.surface("main", UI.text("Hello!").row(UI.button("Click me"))))
 *   agent.ui(UI.form("Login", { fields: [{ label: "Email", bind: "/email" }] }))
 */

import { A2UIError, A2UISurfaceError } from "../_exceptions.js";
import {
  fluxBadge,
  fluxBanner,
  fluxButton,
  fluxCard,
  fluxLink,
  fluxMarkdown,
  fluxProgress,
  fluxSkeleton,
  fluxStack,
  fluxTextField,
  type FluxBadgeArgs,
  type FluxBannerArgs,
  type FluxButtonArgs,
  type FluxCardArgs,
  type FluxLinkArgs,
  type FluxMarkdownArgs,
  type FluxProgressArgs,
  type FluxSkeletonArgs,
  type FluxStackArgs,
  type FluxTextFieldArgs,
} from "../flux/index.js";

// ---------------------------------------------------------------------------
// Catalog dispatch
// ---------------------------------------------------------------------------

/** Known catalog identifiers. Used by UI.withCatalog and T.a2ui. */
export const KNOWN_CATALOGS = Object.freeze(["basic", "flux"] as const);
export type CatalogName = (typeof KNOWN_CATALOGS)[number];

// Module-scoped catalog stack: closure-scoped via withCatalog(name, fn).
// We keep a stack so nested calls restore the right parent on exit.
let _catalogStack: CatalogName[] = ["basic"];

/** Return the currently-active catalog (top of stack). */
export function activeCatalog(): CatalogName {
  return _catalogStack[_catalogStack.length - 1] ?? "basic";
}

function _pushCatalog(name: CatalogName): void {
  _catalogStack = [..._catalogStack, name];
}

function _popCatalog(): void {
  if (_catalogStack.length > 1) {
    _catalogStack = _catalogStack.slice(0, -1);
  }
}

/** Data binding specification. */
export interface UIBinding {
  path: string;
  direction?: "read" | "write" | "readwrite";
}

/** Validation check descriptor. */
export interface UICheck {
  type: string;
  config: Record<string, unknown>;
}

/** UI component descriptor — the universal building block. */
export class UIComponent {
  constructor(
    public readonly kind: string,
    public readonly props: Record<string, unknown> = {},
    public readonly children: UIComponent[] = [],
    public readonly id?: string,
  ) {}

  /** Horizontal composition: wrap this and other in a row. */
  row(...others: UIComponent[]): UIComponent {
    return new UIComponent("Row", {}, [this, ...others]);
  }

  /** Vertical composition: wrap this and other in a column. */
  column(...others: UIComponent[]): UIComponent {
    return new UIComponent("Column", {}, [this, ...others]);
  }

  /** Add child components. */
  add(...children: UIComponent[]): UIComponent {
    return new UIComponent(this.kind, this.props, [...this.children, ...children], this.id);
  }
}

/**
 * Theme marker — produced by ``UI.theme(name)`` and consumed by
 * ``UI.surface(...)`` to populate ``UISurface.theme``. Theme markers are
 * stripped from the surface root so they never appear as components.
 */
export class UIThemeMarker {
  constructor(public readonly name: string) {}
}

/** A named UI surface (compilation root). */
export class UISurface {
  constructor(
    public readonly name: string,
    public readonly root: UIComponent,
    public readonly meta: Record<string, unknown> = {},
    public readonly data: Record<string, unknown> = {},
    public readonly handlers: Record<string, unknown> = {},
    /** Theme attached via ``UI.theme(name)``. Empty object when unset. */
    public readonly theme: { name?: string } = {},
  ) {}

  /**
   * Validate this surface for structural integrity.
   *
   * Checks (in order, fail-first):
   *   1. Component IDs are unique across the tree.
   *   2. Root must be a real component, not a virtual group.
   *   3. Two-way bind paths reference declared `data` keys (skipped if no data).
   *   4. Action event names registered must match handler names (skipped if no handlers).
   *
   * @throws A2UISurfaceError on the first violation discovered.
   */
  validate(): void {
    // 1. Unique IDs
    const seenIds = new Set<string>();
    const visit = (c: UIComponent): void => {
      if (c.id) {
        if (seenIds.has(c.id)) {
          throw new A2UISurfaceError(`Duplicate component id '${c.id}'`, this.name);
        }
        seenIds.add(c.id);
      }
      for (const child of c.children) visit(child);
    };
    visit(this.root);

    // 2. Root must be a real component
    if (!this.root || !this.root.kind || this.root.kind === "VirtualGroup") {
      throw new A2UISurfaceError(
        "Surface root must be a real component (not a virtual group)",
        this.name,
      );
    }

    // 3. Bind paths reference declared data keys (only if data is non-empty)
    const dataKeys = Object.keys(this.data);
    if (dataKeys.length > 0) {
      const checkBindings = (c: UIComponent): void => {
        const bind = c.props.bind as { path?: string } | undefined;
        if (bind?.path) {
          // JSON Pointer like "/email" or "/user/name" — top key must exist in data
          const top = bind.path.replace(/^\//, "").split("/")[0];
          if (top && !dataKeys.includes(top)) {
            throw new A2UISurfaceError(
              `Bind path '${bind.path}' references undeclared data key '${top}'. ` +
                `Declared: ${dataKeys.join(", ")}`,
              this.name,
            );
          }
        }
        for (const child of c.children) checkBindings(child);
      };
      checkBindings(this.root);
    }

    // 4. Action handler names must match (only if handlers registered)
    const handlerNames = Object.keys(this.handlers);
    if (handlerNames.length > 0) {
      const checkActions = (c: UIComponent): void => {
        const action = c.props.action;
        let eventName: string | undefined;
        if (typeof action === "string") {
          eventName = action;
        } else if (action && typeof action === "object" && "event" in action) {
          eventName = (action as { event?: string }).event;
        }
        if (eventName && !handlerNames.includes(eventName)) {
          throw new A2UISurfaceError(
            `Action '${eventName}' has no registered handler. ` +
              `Registered: ${handlerNames.join(", ")}`,
            this.name,
          );
        }
        for (const child of c.children) checkActions(child);
      };
      checkActions(this.root);
    }
  }
}

/**
 * LLM-guided UI mode marker.
 *
 * When passed to `Agent.ui(spec)` (or via `agent.ui(undefined, { llmGuided: true })`),
 * signals that the LLM should be allowed to design the UI surface itself
 * via the A2UI toolset and catalog schema injection.
 */
export class UIAutoSpec {
  readonly fromFlag: boolean;
  constructor(
    public catalog: string = "basic",
    opts: { fromFlag?: boolean } = {},
  ) {
    this.fromFlag = opts.fromFlag ?? false;
  }
}

/**
 * Schema-only prompt injection marker.
 *
 * When passed to `Agent.ui(spec)`, signals that only the catalog schema
 * should be injected into the system prompt — the LLM is not asked to
 * generate UI itself, but is informed of the available components.
 */
export class UISchemaSpec {
  constructor(public catalogUri: string | null = null) {}
}

/**
 * UI namespace — A2UI component factories.
 *
 * All component factories, validation checks, presets, formatting functions,
 * and surface lifecycle from the Python UI namespace.
 */
export class UI {
  // ------------------------------------------------------------------
  // Data binding
  // ------------------------------------------------------------------

  /** Create data binding to a JSON Pointer path. */
  static bind(path: string, opts?: { direction?: "read" | "write" | "readwrite" }): UIBinding {
    return { path, direction: opts?.direction ?? "readwrite" };
  }

  /** Format string with ${/path} interpolation. */
  static fmt(template: string): Record<string, unknown> {
    return { type: "formatString", template };
  }

  // ------------------------------------------------------------------
  // Surface lifecycle
  // ------------------------------------------------------------------

  /**
   * Create a named UI surface (compilation root).
   *
   * The ``root`` argument may be a plain ``UIComponent`` (standard) or an
   * array mixing components and ``UIThemeMarker``. Theme markers are lifted
   * off the root list and attached to ``UISurface.theme`` — never rendered.
   *
   * When multiple theme markers are present the last one wins; when multiple
   * components are present without an explicit root a ``UIError`` is thrown.
   */
  static surface(
    name: string,
    root: UIComponent | Array<UIComponent | UIThemeMarker>,
    meta?: Record<string, unknown>,
  ): UISurface {
    let theme: { name?: string } = {};
    let resolved: UIComponent;

    if (Array.isArray(root)) {
      const comps: UIComponent[] = [];
      for (const item of root) {
        if (item instanceof UIThemeMarker) {
          theme = { name: item.name };
        } else {
          comps.push(item);
        }
      }
      if (comps.length === 0) {
        throw new A2UIError(
          `UI.surface(${JSON.stringify(name)}) needs at least one component root`,
        );
      }
      if (comps.length > 1) {
        throw new A2UIError(
          `UI.surface(${JSON.stringify(name)}) expects a single root component; got ${comps.length}`,
        );
      }
      resolved = comps[0]!;
    } else {
      resolved = root;
    }

    return new UISurface(name, resolved, meta, {}, {}, theme);
  }

  /**
   * Attach a theme id to the enclosing surface.
   *
   * Use inline with ``UI.surface``::
   *
   *     UI.surface("demo", [UI.theme("flux-dark"), UI.column([...])])
   *
   * The compiled surface carries ``createSurface.theme = { name: "<id>" }``.
   */
  static theme(name: string): UIThemeMarker {
    return new UIThemeMarker(name);
  }

  /**
   * Scoped catalog dispatch.
   *
   * Runs ``fn`` with the given catalog active; all ``UI.button`` / ``.badge``
   * / ``.card`` / etc. calls inside the callback emit the catalog-specific
   * components (e.g. ``FluxButton`` when catalog is ``"flux"``). Catalog
   * state is restored on return (including across thrown errors).
   *
   * Nests cleanly. Unknown catalogs throw ``A2UIError``.
   */
  static withCatalog<T>(name: CatalogName | string, fn: () => T): T {
    if (!KNOWN_CATALOGS.includes(name as CatalogName)) {
      throw new A2UIError(
        `Unknown catalog ${JSON.stringify(name)}. Known catalogs: ${JSON.stringify([
          ...KNOWN_CATALOGS,
        ])}`,
      );
    }
    _pushCatalog(name as CatalogName);
    try {
      return fn();
    } finally {
      _popCatalog();
    }
  }

  /** Catalog-agnostic component factory (escape hatch). */
  static component(kind: string, opts?: { id?: string; [key: string]: unknown }): UIComponent {
    const { id, ...props } = opts ?? {};
    return new UIComponent(kind, props, [], id);
  }

  // ------------------------------------------------------------------
  // Flux overload dispatch helper
  // ------------------------------------------------------------------

  /**
   * Lift a flux factory's dict result into a UIComponent so flux nodes
   * compose with basic-catalog components via .row() / .column() / .add().
   */
  private static _fluxNodeToComponent(
    node: { component: string; id: string } & object,
  ): UIComponent {
    const asRecord = node as unknown as Record<string, unknown>;
    const kind = String(asRecord.component ?? "");
    const id = typeof asRecord.id === "string" ? asRecord.id : undefined;
    const props: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(asRecord)) {
      if (k !== "component" && k !== "id") props[k] = v;
    }
    return new UIComponent(kind, props, [], id);
  }

  // ------------------------------------------------------------------
  // LLM-guided mode
  // ------------------------------------------------------------------

  /** LLM-guided mode: inject catalog schema so agent decides UI. */
  static auto(opts?: { catalog?: string; fromFlag?: boolean }): UIAutoSpec {
    return new UIAutoSpec(opts?.catalog ?? "basic", { fromFlag: opts?.fromFlag });
  }

  /** Schema-only prompt injection (no auto mode). */
  static schema(catalogUri?: string): UISchemaSpec {
    return new UISchemaSpec(catalogUri ?? null);
  }

  // ------------------------------------------------------------------
  // Text & media components
  // ------------------------------------------------------------------

  /** Text content component. */
  static text(
    content: string,
    opts?: { variant?: "h1" | "h2" | "h3" | "h4" | "h5" | "caption" | "body"; id?: string },
  ): UIComponent {
    return new UIComponent(
      "Text",
      {
        text: content,
        variant: opts?.variant ?? "body",
      },
      [],
      opts?.id,
    );
  }

  /** Heading sugar (alias for UI.text with variant='h1'). */
  static heading(content: string, opts?: { id?: string }): UIComponent {
    return UI.text(content, { variant: "h1", ...opts });
  }

  /** Image component. */
  static image(
    url: string,
    opts?: { fit?: "contain" | "cover" | "fill"; variant?: string; id?: string },
  ): UIComponent {
    return new UIComponent(
      "Image",
      {
        url,
        fit: opts?.fit ?? "contain",
        variant: opts?.variant,
      },
      [],
      opts?.id,
    );
  }

  /** Icon component. */
  static icon(name: string, opts?: { id?: string }): UIComponent {
    return new UIComponent("Icon", { name }, [], opts?.id);
  }

  /** Video player component. */
  static video(url: string, opts?: { id?: string }): UIComponent {
    return new UIComponent("Video", { url }, [], opts?.id);
  }

  /** Audio player component. */
  static audio(url: string, opts?: { description?: string; id?: string }): UIComponent {
    return new UIComponent(
      "Audio",
      {
        url,
        description: opts?.description,
      },
      [],
      opts?.id,
    );
  }

  // ------------------------------------------------------------------
  // Layout components
  // ------------------------------------------------------------------

  /** Horizontal layout. */
  static row(
    children: UIComponent[],
    opts?: { justify?: string; align?: string; id?: string },
  ): UIComponent {
    return new UIComponent(
      "Row",
      {
        justify: opts?.justify,
        align: opts?.align,
      },
      children,
      opts?.id,
    );
  }

  /** Vertical layout. */
  static column(
    children: UIComponent[],
    opts?: { justify?: string; align?: string; id?: string },
  ): UIComponent {
    return new UIComponent(
      "Column",
      {
        justify: opts?.justify,
        align: opts?.align,
      },
      children,
      opts?.id,
    );
  }

  /** List layout. */
  static list(
    children: UIComponent[],
    opts?: { direction?: "horizontal" | "vertical"; align?: string; id?: string },
  ): UIComponent {
    return new UIComponent(
      "List",
      {
        direction: opts?.direction ?? "vertical",
        align: opts?.align,
      },
      children,
      opts?.id,
    );
  }

  /**
   * Card container.
   *
   * Catalog dispatch:
   * - **basic** (default): wraps a child component in a ``Card``.
   * - **flux**: emits a ``FluxCard`` with the given flux args (see
   *   ``FluxCardArgs``). When called as ``UI.card(component, {...})`` inside
   *   a flux scope the positional component is ignored and a ``FluxCard``
   *   is synthesised from the opts.
   */
  static card(): UIComponent;
  static card(child: UIComponent, opts?: { id?: string }): UIComponent;
  static card(args: FluxCardArgs): UIComponent;
  static card(childOrArgs?: UIComponent | FluxCardArgs, opts?: { id?: string }): UIComponent {
    if (activeCatalog() === "flux") {
      // Flux path: accept FluxCardArgs (with id, emphasis, padding, body, …).
      const args: FluxCardArgs = {
        id: "card",
        emphasis: "subtle",
        padding: "md",
        body: "",
        ...((childOrArgs && !(childOrArgs instanceof UIComponent)
          ? childOrArgs
          : {}) as Partial<FluxCardArgs>),
      };
      return UI._fluxNodeToComponent(fluxCard(args));
    }
    // Basic path: preserve legacy (child, opts) signature.
    const child = childOrArgs as UIComponent | undefined;
    if (!child) {
      throw new A2UIError("UI.card() (basic catalog) requires a child component");
    }
    return new UIComponent("Card", {}, [child], opts?.id);
  }

  /** Tabbed interface. */
  static tabs(
    tabs: Array<{ label: string; content: UIComponent }>,
    opts?: { id?: string },
  ): UIComponent {
    return new UIComponent("Tabs", { tabs }, [], opts?.id);
  }

  /** Modal dialog. */
  static modal(child: UIComponent, opts?: { id?: string }): UIComponent {
    return new UIComponent("Modal", {}, [child], opts?.id);
  }

  /** Divider. */
  static divider(opts?: { axis?: "horizontal" | "vertical"; id?: string }): UIComponent {
    return new UIComponent(
      "Divider",
      {
        axis: opts?.axis ?? "horizontal",
      },
      [],
      opts?.id,
    );
  }

  // ------------------------------------------------------------------
  // Input components
  // ------------------------------------------------------------------

  /**
   * Button component.
   *
   * Catalog dispatch:
   * - **basic** (default): emits a ``Button`` with a Text child label and
   *   the standard ``variant`` / ``action`` / ``checks`` options.
   * - **flux**: emits a ``FluxButton``. Accepts either the legacy
   *   ``(label, opts)`` call style (label becomes ``args.label``, ``tone``
   *   defaulted to ``"primary"``) or a full ``FluxButtonArgs`` object.
   */
  static button(
    label: string,
    opts?: {
      variant?: "default" | "primary" | "borderless";
      tone?: "neutral" | "primary" | "danger" | "success";
      size?: "sm" | "md" | "lg";
      emphasis?: "solid" | "soft" | "outline" | "ghost";
      action?: string | Record<string, unknown>;
      checks?: UICheck[];
      accessibility?: Record<string, unknown>;
      id?: string;
    },
  ): UIComponent;
  static button(args: FluxButtonArgs): UIComponent;
  static button(
    labelOrArgs: string | FluxButtonArgs,
    opts?: {
      variant?: "default" | "primary" | "borderless";
      tone?: "neutral" | "primary" | "danger" | "success";
      size?: "sm" | "md" | "lg";
      emphasis?: "solid" | "soft" | "outline" | "ghost";
      action?: string | Record<string, unknown>;
      checks?: UICheck[];
      accessibility?: Record<string, unknown>;
      id?: string;
    },
  ): UIComponent {
    if (activeCatalog() === "flux") {
      if (typeof labelOrArgs === "string") {
        // Legacy-shaped call: promote to FluxButtonArgs.
        const label = labelOrArgs;
        const action = opts?.action;
        const args: FluxButtonArgs = {
          id: opts?.id ?? "btn",
          tone: opts?.tone ?? "primary",
          size: opts?.size ?? "md",
          emphasis: opts?.emphasis ?? "solid",
          action:
            typeof action === "string"
              ? { event: action }
              : ((action ?? {}) as Record<string, unknown>),
          accessibility: opts?.accessibility ?? { label },
          label,
        };
        return UI._fluxNodeToComponent(fluxButton(args));
      }
      return UI._fluxNodeToComponent(fluxButton(labelOrArgs));
    }

    // Basic path: preserve legacy UIComponent shape.
    const label = typeof labelOrArgs === "string" ? labelOrArgs : String(labelOrArgs.label ?? "");
    return new UIComponent(
      "Button",
      {
        child: { type: "Text", text: label },
        variant: opts?.variant ?? "default",
        action: opts?.action,
        checks: opts?.checks,
      },
      [],
      opts?.id,
    );
  }

  /**
   * Text input field.
   *
   * Catalog dispatch:
   * - **basic** (default): emits a ``TextField`` with ``variant``,
   *   ``bind``, ``checks``, ``value`` — unchanged from prior versions.
   * - **flux**: emits a ``FluxTextField``. Accepts either the legacy
   *   ``(label, opts)`` call (label is lifted into ``accessibility.label``)
   *   or a full ``FluxTextFieldArgs`` object.
   */
  static textField(
    label: string,
    opts?: {
      value?: string;
      variant?: "shortText" | "longText" | "number" | "obscured";
      type?: "text" | "email" | "password" | "number" | "search" | "tel" | "url";
      size?: "sm" | "md" | "lg";
      state?: "default" | "error" | "success" | "warning";
      placeholder?: string;
      helper?: string;
      bind?: UIBinding;
      checks?: UICheck[];
      accessibility?: Record<string, unknown>;
      id?: string;
    },
  ): UIComponent;
  static textField(args: FluxTextFieldArgs): UIComponent;
  static textField(
    labelOrArgs: string | FluxTextFieldArgs,
    opts?: {
      value?: string;
      variant?: "shortText" | "longText" | "number" | "obscured";
      type?: "text" | "email" | "password" | "number" | "search" | "tel" | "url";
      size?: "sm" | "md" | "lg";
      state?: "default" | "error" | "success" | "warning";
      placeholder?: string;
      helper?: string;
      bind?: UIBinding;
      checks?: UICheck[];
      accessibility?: Record<string, unknown>;
      id?: string;
    },
  ): UIComponent {
    if (activeCatalog() === "flux") {
      if (typeof labelOrArgs === "string") {
        const label = labelOrArgs;
        const args: FluxTextFieldArgs = {
          id: opts?.id ?? "tf",
          type: opts?.type ?? "text",
          size: opts?.size ?? "md",
          state: opts?.state ?? "default",
          accessibility: opts?.accessibility ?? { label },
          ...(opts?.placeholder !== undefined && { placeholder: opts.placeholder }),
          ...(opts?.helper !== undefined && { helper: opts.helper }),
          ...(opts?.value !== undefined && { value: opts.value }),
        };
        return UI._fluxNodeToComponent(fluxTextField(args));
      }
      return UI._fluxNodeToComponent(fluxTextField(labelOrArgs));
    }

    const label = typeof labelOrArgs === "string" ? labelOrArgs : "";
    return new UIComponent(
      "TextField",
      {
        label,
        value: opts?.value ?? "",
        variant: opts?.variant ?? "shortText",
        bind: opts?.bind,
        checks: opts?.checks,
      },
      [],
      opts?.id,
    );
  }

  // ------------------------------------------------------------------
  // Flux-specific factories (only meaningful inside UI.withCatalog("flux"))
  // ------------------------------------------------------------------

  /**
   * Flux badge — compact label for status, counts, tags. Not clickable.
   * Only meaningful inside ``UI.withCatalog("flux", ...)``. Outside a flux
   * scope, falls back to a plain ``Text`` component with the label so
   * basic-catalog surfaces render something sensible.
   */
  static badge(label: string, opts?: Partial<FluxBadgeArgs>): UIComponent {
    if (activeCatalog() === "flux") {
      const args: FluxBadgeArgs = {
        id: opts?.id ?? "badge",
        label,
        tone: opts?.tone ?? "neutral",
        variant: opts?.variant ?? "subtle",
        size: opts?.size ?? "sm",
        ...(opts?.accessibility && { accessibility: opts.accessibility }),
      };
      return UI._fluxNodeToComponent(fluxBadge(args));
    }
    // Basic fallback: catalog.json maps FluxBadge → Text.
    return UI.text(label, { variant: "caption" });
  }

  /**
   * Flux progress indicator. Set ``determinate: true`` with a ``value`` in
   * 0..100 for known ratios; ``determinate: false`` for indeterminate spin.
   * Outside a flux scope, falls back to the basic ``Slider`` preview.
   */
  static progress(opts?: Partial<FluxProgressArgs>): UIComponent {
    if (activeCatalog() === "flux") {
      const args: FluxProgressArgs = {
        id: opts?.id ?? "progress",
        value: opts?.value ?? 0,
        determinate: opts?.determinate ?? true,
        tone: opts?.tone ?? "default",
        size: opts?.size ?? "md",
        accessibility: opts?.accessibility ?? { label: "progress" },
        ...(opts?.label !== undefined && { label: opts.label }),
      };
      return UI._fluxNodeToComponent(fluxProgress(args));
    }
    return UI.slider({
      value: opts?.value ?? 0,
      min: 0,
      max: 100,
      id: opts?.id,
    });
  }

  /**
   * Flux skeleton — loading-state placeholder. ``shape=text`` for paragraph
   * rows, ``shape=circle`` for avatars, ``shape=rect`` for cards/images.
   * Outside flux, falls back to a muted Text placeholder.
   */
  static skeleton(opts?: Partial<FluxSkeletonArgs>): UIComponent {
    if (activeCatalog() === "flux") {
      const args: FluxSkeletonArgs = {
        id: opts?.id ?? "skeleton",
        shape: opts?.shape ?? "text",
        size: opts?.size ?? "md",
        ...(opts?.count !== undefined && { count: opts.count }),
        ...(opts?.height !== undefined && { height: opts.height }),
        ...(opts?.width !== undefined && { width: opts.width }),
        ...(opts?.accessibility && { accessibility: opts.accessibility }),
      };
      return UI._fluxNodeToComponent(fluxSkeleton(args));
    }
    return UI.text("…", { variant: "caption" });
  }

  /**
   * Flux markdown — prose block rendered from a Markdown source string.
   * Outside flux, renders as a plain ``Text`` body with the raw source.
   */
  static markdown(source: string, opts?: Partial<FluxMarkdownArgs>): UIComponent {
    if (activeCatalog() === "flux") {
      const args: FluxMarkdownArgs = {
        id: opts?.id ?? "md",
        source,
        size: opts?.size ?? "md",
        proseStyle: opts?.proseStyle ?? "default",
        ...(opts?.accessibility && { accessibility: opts.accessibility }),
      };
      return UI._fluxNodeToComponent(fluxMarkdown(args));
    }
    return UI.text(source, { variant: "body" });
  }

  /**
   * Flux link — inline hyperlink. Set ``href`` for navigation *or*
   * ``action`` for an auth-gated dispatch — never both.
   * Outside flux, falls back to a plain ``Text`` with the label.
   */
  static link(label: string, opts?: Partial<FluxLinkArgs>): UIComponent {
    if (activeCatalog() === "flux") {
      const args: FluxLinkArgs = {
        id: opts?.id ?? "link",
        label,
        tone: opts?.tone ?? "default",
        underline: opts?.underline ?? "hover",
        ...(opts?.href !== undefined && { href: opts.href }),
        ...(opts?.action && { action: opts.action }),
        ...(opts?.external !== undefined && { external: opts.external }),
        ...(opts?.accessibility && { accessibility: opts.accessibility }),
      };
      return UI._fluxNodeToComponent(fluxLink(args));
    }
    return UI.text(label, { variant: "body" });
  }

  /**
   * Flux banner — inline notification row. ``info``/``success`` use
   * ``role=status``; ``warning``/``danger`` use ``role=alert``.
   * Outside flux, falls back to a simple two-line ``Column``.
   */
  static banner(opts: { title: string; message: string } & Partial<FluxBannerArgs>): UIComponent {
    if (activeCatalog() === "flux") {
      const args: FluxBannerArgs = {
        id: opts.id ?? "banner",
        title: opts.title,
        message: opts.message,
        tone: opts.tone ?? "info",
        ...(opts.action !== undefined && { action: opts.action }),
        ...(opts.dismiss !== undefined && { dismiss: opts.dismiss }),
        ...(opts.icon !== undefined && { icon: opts.icon }),
        ...(opts.accessibility && { accessibility: opts.accessibility }),
      };
      return UI._fluxNodeToComponent(fluxBanner(args));
    }
    return UI.column([
      UI.text(opts.title, { variant: "h3" }),
      UI.text(opts.message, { variant: "body" }),
    ]);
  }

  /**
   * Flux stack — layout primitive for arranging children with consistent
   * spacing. Only meaningful inside a flux scope; outside, falls back to
   * a ``Column`` with no children (callers add children post-hoc via
   * ``.add(...)``).
   */
  static stack(opts?: Partial<FluxStackArgs>): UIComponent {
    if (activeCatalog() === "flux") {
      const args: FluxStackArgs = {
        id: opts?.id ?? "stack",
        direction: opts?.direction ?? "vertical",
        gap: opts?.gap ?? "2",
        align: opts?.align ?? "stretch",
        justify: opts?.justify ?? "start",
        ...(opts?.wrap !== undefined && { wrap: opts.wrap }),
        ...(opts?.accessibility && { accessibility: opts.accessibility }),
      };
      return UI._fluxNodeToComponent(fluxStack(args));
    }
    return UI.column([]);
  }

  /** Checkbox component. */
  static checkbox(
    label: string,
    opts?: { value?: boolean; bind?: UIBinding; checks?: UICheck[]; id?: string },
  ): UIComponent {
    return new UIComponent(
      "Checkbox",
      {
        label,
        value: opts?.value ?? false,
        bind: opts?.bind,
        checks: opts?.checks,
      },
      [],
      opts?.id,
    );
  }

  /** Choice picker (select / radio). */
  static choice(
    options: Array<string | { label: string; value: unknown }>,
    opts?: {
      value?: unknown;
      label?: string;
      variant?: "dropdown" | "radio" | "chips";
      displayStyle?: string;
      filterable?: boolean;
      bind?: UIBinding;
      checks?: UICheck[];
      id?: string;
    },
  ): UIComponent {
    return new UIComponent(
      "Choice",
      {
        options,
        value: opts?.value,
        label: opts?.label,
        variant: opts?.variant ?? "dropdown",
        displayStyle: opts?.displayStyle,
        filterable: opts?.filterable ?? false,
        bind: opts?.bind,
        checks: opts?.checks,
      },
      [],
      opts?.id,
    );
  }

  /** Slider component. */
  static slider(opts?: {
    max?: number;
    value?: number;
    label?: string;
    min?: number;
    bind?: UIBinding;
    checks?: UICheck[];
    id?: string;
  }): UIComponent {
    return new UIComponent(
      "Slider",
      {
        min: opts?.min ?? 0,
        max: opts?.max ?? 100,
        value: opts?.value ?? 50,
        label: opts?.label,
        bind: opts?.bind,
        checks: opts?.checks,
      },
      [],
      opts?.id,
    );
  }

  /** DateTime input component. */
  static dateTime(opts?: {
    value?: string;
    enableDate?: boolean;
    enableTime?: boolean;
    min?: string;
    max?: string;
    label?: string;
    bind?: UIBinding;
    checks?: UICheck[];
    id?: string;
  }): UIComponent {
    return new UIComponent(
      "DateTime",
      {
        value: opts?.value,
        enableDate: opts?.enableDate ?? true,
        enableTime: opts?.enableTime ?? false,
        min: opts?.min,
        max: opts?.max,
        label: opts?.label,
        bind: opts?.bind,
        checks: opts?.checks,
      },
      [],
      opts?.id,
    );
  }

  // ------------------------------------------------------------------
  // Validation checks (return UICheck)
  // ------------------------------------------------------------------

  /** Required value check. */
  static required(msg?: string): UICheck {
    return { type: "required", config: { message: msg ?? "This field is required" } };
  }

  /** Regex pattern check. */
  static regex(pattern: string, msg?: string): UICheck {
    return { type: "regex", config: { pattern, message: msg ?? `Must match ${pattern}` } };
  }

  /** String length check. */
  static length(opts: { min?: number; max?: number; msg?: string }): UICheck {
    return { type: "length", config: { min: opts.min, max: opts.max, message: opts.msg } };
  }

  /** Numeric range check. */
  static numeric(opts: { min?: number; max?: number; msg?: string }): UICheck {
    return { type: "numeric", config: { min: opts.min, max: opts.max, message: opts.msg } };
  }

  /** Email format check. */
  static email(msg?: string): UICheck {
    return { type: "email", config: { message: msg ?? "Invalid email address" } };
  }

  // ------------------------------------------------------------------
  // Formatting functions
  // ------------------------------------------------------------------

  /** String interpolation function. */
  static formatString(): Record<string, unknown> {
    return { type: "formatString" };
  }

  /** Number formatting. */
  static formatNumber(opts?: { decimals?: number; grouping?: boolean }): Record<string, unknown> {
    return {
      type: "formatNumber",
      decimals: opts?.decimals ?? 0,
      grouping: opts?.grouping ?? true,
    };
  }

  /** Currency formatting. */
  static formatCurrency(opts?: {
    currency?: string;
    decimals?: number;
    grouping?: boolean;
  }): Record<string, unknown> {
    return {
      type: "formatCurrency",
      currency: opts?.currency ?? "USD",
      decimals: opts?.decimals ?? 2,
      grouping: opts?.grouping ?? true,
    };
  }

  /** Date formatting. */
  static formatDate(format?: string): Record<string, unknown> {
    return { type: "formatDate", format: format ?? "yyyy-MM-dd" };
  }

  /** Localized pluralization. */
  static pluralize(opts: {
    other: string;
    zero?: string;
    one?: string;
    two?: string;
    few?: string;
    many?: string;
  }): Record<string, unknown> {
    return { type: "pluralize", ...opts };
  }

  // ------------------------------------------------------------------
  // Logic functions
  // ------------------------------------------------------------------

  /** Logical AND. */
  static and(values: unknown[]): Record<string, unknown> {
    return { type: "and", values };
  }

  /** Logical OR. */
  static or(values: unknown[]): Record<string, unknown> {
    return { type: "or", values };
  }

  /** Logical NOT. */
  static not(): Record<string, unknown> {
    return { type: "not" };
  }

  // ------------------------------------------------------------------
  // Utility
  // ------------------------------------------------------------------

  /** Open URL action. */
  static openUrl(url: string): Record<string, unknown> {
    return { type: "openUrl", url };
  }

  // ------------------------------------------------------------------
  // Preset surfaces
  // ------------------------------------------------------------------

  /**
   * Generate a form surface from a field spec or a Zod object schema.
   *
   * Two call signatures (auto-detected):
   *
   *   - **Schema path** — `UI.form(z.object({...}), opts?)`: derives fields,
   *     types, validation checks, and bind paths from the Zod schema. The
   *     dependency on Zod is *optional* (peer dependency). When you pass a
   *     Zod object, this method introspects it via `schema.def.shape` /
   *     `schema.def.checks` (Zod v4 public API).
   *
   *   - **Legacy path** — `UI.form("title", { fields: [...] })`: explicit
   *     field-spec list. Unchanged from prior versions.
   *
   * Throws `A2UIError` when the first argument is neither a Zod object nor a
   * string.
   */
  static form(
    schemaOrTitle: unknown,
    opts?: {
      title?: string;
      fields?: Array<{ label: string; bind?: string; type?: string; required?: boolean }>;
      submit?: string;
      submitAction?: string | Record<string, unknown>;
    },
  ): UISurface {
    // Detect Zod object schema (duck-typed against v4 public API).
    if (UI._isZodObject(schemaOrTitle)) {
      return UI._formFromZod(schemaOrTitle, opts ?? {});
    }
    if (typeof schemaOrTitle === "string") {
      const title = schemaOrTitle;
      const fields = opts?.fields ?? [];
      const fieldComponents = fields.map((f) => {
        const checks: UICheck[] = [];
        if (f.required) checks.push(UI.required());
        return UI.textField(f.label, {
          variant: (f.type ?? "shortText") as "shortText" | "longText",
          bind: f.bind ? UI.bind(f.bind) : undefined,
          checks: checks.length > 0 ? checks : undefined,
        });
      });
      const submitBtn = UI.button(opts?.submit ?? "Submit", {
        variant: "primary",
        action: opts?.submitAction,
      });
      const root = UI.column([UI.heading(title), ...fieldComponents, submitBtn]);
      return new UISurface(title.toLowerCase().replace(/\s+/g, "_"), root);
    }
    throw new A2UIError("UI.form expects either a Zod object schema or (title, opts.fields)");
  }

  /**
   * Build a typed proxy that returns `UI.bind(path)` instances for every
   * field declared in a Zod object schema. Nested objects produce nested
   * proxies — accessing them keeps the JSON-Pointer prefix for free.
   *
   * Example:
   *   const Schema = z.object({ email: z.string(), profile: z.object({ age: z.number() }) });
   *   const paths = UI.paths(Schema);
   *   UI.text_field("Email", { bind: paths.email });           // → { path: "/email", ... }
   *   UI.text_field("Age",   { bind: paths.profile.age });     // → { path: "/profile/age", ... }
   *
   * Accessing a non-existent field throws A2UIError listing valid keys.
   */
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  static paths<T = any>(schema: unknown): T {
    if (!UI._isZodObject(schema)) {
      throw new A2UIError("UI.paths expects a Zod object schema");
    }
    const make = (sch: unknown, prefix = ""): unknown =>
      new Proxy(
        {},
        {
          get(_t, prop) {
            if (typeof prop !== "string") return undefined;
            const shape = UI._zodObjectShape(sch);
            if (!shape || !(prop in shape)) {
              throw new A2UIError(
                `Schema has no field '${String(prop)}'. ` +
                  `Available: ${Object.keys(shape ?? {}).join(", ")}`,
              );
            }
            const inner = UI._unwrapZod(shape[prop]);
            const path = `${prefix}/${prop}`;
            if (UI._isZodObject(inner)) {
              return make(inner, path);
            }
            return UI.bind(path);
          },
        },
      );
    return make(schema) as T;
  }

  // ------------------------------------------------------------------
  // Zod v4 introspection helpers
  // ------------------------------------------------------------------

  /** Detect a Zod object schema via duck-typing the v4 public `def` surface. */
  private static _isZodObject(value: unknown): value is {
    def: { type: string; shape: Record<string, unknown> };
    shape: Record<string, unknown>;
  } {
    if (!value || typeof value !== "object") return false;
    const v = value as { def?: { type?: string }; shape?: unknown };
    return v.def?.type === "object" && typeof v.shape === "object" && v.shape !== null;
  }

  /** Read the `shape` from a Zod object (v4 exposes it on both `.shape` and `.def.shape`). */
  private static _zodObjectShape(value: unknown): Record<string, unknown> | null {
    if (!value || typeof value !== "object") return null;
    const v = value as {
      shape?: Record<string, unknown>;
      def?: { shape?: Record<string, unknown> };
    };
    return (v.shape ?? v.def?.shape ?? null) as Record<string, unknown> | null;
  }

  /** Unwrap optional / nullable wrappers, returning the inner schema. */
  private static _unwrapZod(value: unknown): unknown {
    let cur: unknown = value;
    let guard = 0;
    while (cur && typeof cur === "object" && guard++ < 8) {
      const v = cur as { def?: { type?: string; innerType?: unknown }; unwrap?: () => unknown };
      const t = v.def?.type;
      if (t === "optional" || t === "nullable") {
        if (typeof v.unwrap === "function") {
          cur = v.unwrap();
        } else {
          cur = v.def?.innerType;
        }
        continue;
      }
      break;
    }
    return cur;
  }

  /** Detect optional/nullable wrapper. */
  private static _isZodOptional(value: unknown): boolean {
    if (!value || typeof value !== "object") return false;
    const t = (value as { def?: { type?: string } }).def?.type;
    return t === "optional" || t === "nullable";
  }

  /** Build a UISurface from a Zod object schema. */
  private static _formFromZod(
    schema: unknown,
    opts: {
      title?: string;
      submit?: string;
      submitAction?: string | Record<string, unknown>;
    },
  ): UISurface {
    const shape = UI._zodObjectShape(schema);
    if (!shape) {
      throw new A2UIError("UI.form: unable to read object shape from Zod schema");
    }
    const title = opts.title ?? "Form";
    const fieldComponents: UIComponent[] = [];
    const data: Record<string, unknown> = {};

    for (const [name, rawField] of Object.entries(shape)) {
      const isOptional = UI._isZodOptional(rawField);
      const field = UI._unwrapZod(rawField);
      const label = UI._labelFor(name, field);
      const bind = UI.bind(`/${name}`);
      const checks: UICheck[] = [];
      if (!isOptional) checks.push(UI.required());

      data[name] = null;

      const def = (field as { def?: { type?: string } }).def;
      const fieldType = def?.type;

      if (fieldType === "string") {
        const fmt = (field as { format?: string | null }).format ?? null;
        const stringChecks = (field as { def: { checks?: unknown[] } }).def.checks ?? [];

        // Format-specific (email / url / regex)
        let regexAdded = false;
        let formatHandled = false;
        if (fmt === "email") {
          checks.push(UI.email());
          formatHandled = true;
        } else if (fmt === "url") {
          checks.push(UI.regex("^https?://", "Must be a valid URL"));
          formatHandled = true;
        } else if (fmt === "regex") {
          for (const c of stringChecks) {
            const cd = UI._checkDef(c);
            if (cd?.format === "regex" && cd.pattern instanceof RegExp) {
              checks.push(UI.regex((cd.pattern as RegExp).source));
              regexAdded = true;
            }
          }
          formatHandled = true;
        }

        // Length checks
        let minLen: number | undefined;
        let maxLen: number | undefined;
        for (const c of stringChecks) {
          const cd = UI._checkDef(c);
          if (!cd) continue;
          if (cd.check === "min_length" && typeof cd.minimum === "number") minLen = cd.minimum;
          if (cd.check === "max_length" && typeof cd.maximum === "number") maxLen = cd.maximum;
          if (cd.check === "length_equals" && typeof cd.length === "number") {
            minLen = cd.length;
            maxLen = cd.length;
          }
          // Inline regex check (.regex(...) appended after a format)
          if (
            !regexAdded &&
            cd.check === "string_format" &&
            cd.format === "regex" &&
            cd.pattern instanceof RegExp &&
            !formatHandled
          ) {
            checks.push(UI.regex((cd.pattern as RegExp).source));
            regexAdded = true;
          }
        }
        if (minLen !== undefined || maxLen !== undefined) {
          checks.push(UI.length({ min: minLen, max: maxLen }));
        }
        fieldComponents.push(
          UI.textField(label, {
            variant: "shortText",
            bind,
            checks: checks.length > 0 ? checks : undefined,
          }),
        );
      } else if (fieldType === "number") {
        const numChecks = (field as { def: { checks?: unknown[] } }).def.checks ?? [];
        let minVal: number | undefined;
        let maxVal: number | undefined;
        for (const c of numChecks) {
          const cd = UI._checkDef(c);
          if (!cd) continue;
          if (cd.check === "greater_than" && typeof cd.value === "number") {
            minVal = cd.inclusive ? cd.value : cd.value + Number.EPSILON;
          }
          if (cd.check === "less_than" && typeof cd.value === "number") {
            maxVal = cd.inclusive ? cd.value : cd.value - Number.EPSILON;
          }
        }
        if (minVal !== undefined || maxVal !== undefined) {
          checks.push(UI.numeric({ min: minVal, max: maxVal }));
        }
        fieldComponents.push(
          UI.textField(label, {
            variant: "number",
            bind,
            checks: checks.length > 0 ? checks : undefined,
          }),
        );
      } else if (fieldType === "boolean") {
        // Booleans use Checkbox; required check doesn't apply the same way but keep semantic.
        fieldComponents.push(
          UI.checkbox(label, {
            bind,
            checks: checks.length > 0 ? checks : undefined,
          }),
        );
      } else if (fieldType === "date") {
        fieldComponents.push(
          UI.dateTime({
            label,
            enableDate: true,
            bind,
            checks: checks.length > 0 ? checks : undefined,
          }),
        );
      } else if (fieldType === "enum" || fieldType === "literal") {
        const entries = (
          field as { def: { entries?: Record<string, unknown>; values?: unknown[] } }
        ).def;
        const options: string[] = entries.entries
          ? Object.keys(entries.entries)
          : Array.isArray(entries.values)
            ? (entries.values as unknown[]).map((v) => String(v))
            : [];
        fieldComponents.push(
          UI.choice(options, {
            label,
            variant: "dropdown",
            bind,
            checks: checks.length > 0 ? checks : undefined,
          }),
        );
      } else if (fieldType === "array") {
        const element = (field as { def: { element?: unknown } }).def.element;
        const elDef = (element as { def?: { type?: string } } | undefined)?.def;
        if (elDef?.type === "enum") {
          const entries = (element as { def: { entries?: Record<string, unknown> } }).def.entries;
          const options = entries ? Object.keys(entries) : [];
          fieldComponents.push(
            UI.choice(options, {
              label,
              variant: "chips",
              bind,
              checks: checks.length > 0 ? checks : undefined,
            }),
          );
        } else {
          console.warn(
            `[UI.form] unsupported array element type for field '${name}'; falling back to TextField`,
          );
          fieldComponents.push(
            UI.textField(label, {
              variant: "shortText",
              bind,
              checks: checks.length > 0 ? checks : undefined,
            }),
          );
        }
      } else {
        console.warn(
          `[UI.form] unsupported zod type '${fieldType ?? "unknown"}' for field '${name}'; falling back to TextField shortText`,
        );
        fieldComponents.push(
          UI.textField(label, {
            variant: "shortText",
            bind,
            checks: checks.length > 0 ? checks : undefined,
          }),
        );
      }
    }

    const submitBtn = UI.button(opts.submit ?? "Submit", {
      variant: "primary",
      action: opts.submitAction,
    });
    const root = UI.column([UI.heading(title), ...fieldComponents, submitBtn]);
    return new UISurface(title.toLowerCase().replace(/\s+/g, "_"), root, {}, data);
  }

  /** Pull `def` off a check (Zod v4 stores it under `_zod.def`). */
  private static _checkDef(c: unknown): Record<string, unknown> | null {
    if (!c || typeof c !== "object") return null;
    const cz = c as { _zod?: { def?: Record<string, unknown> }; def?: Record<string, unknown> };
    return cz._zod?.def ?? cz.def ?? null;
  }

  /** Compute label: prefer schema description, else snake_case → Title Case. */
  private static _labelFor(name: string, field: unknown): string {
    const desc = (field as { description?: string }).description;
    if (desc) return desc;
    return name
      .replace(/[_-]+/g, " ")
      .replace(/([a-z])([A-Z])/g, "$1 $2")
      .split(/\s+/)
      .filter(Boolean)
      .map((w) => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase())
      .join(" ");
  }

  /** Generate a dashboard with metric cards. */
  static dashboard(
    title: string,
    opts: { cards: Array<{ label: string; bind?: string; value?: string }> },
  ): UISurface {
    const cardComponents = opts.cards.map((c) =>
      UI.card(
        UI.column([
          UI.text(c.label, { variant: "caption" }),
          UI.text(c.value ?? "", { variant: "h3" }),
        ]),
      ),
    );
    const root = UI.column([UI.heading(title), UI.row(cardComponents)]);
    return new UISurface(title.toLowerCase().replace(/\s+/g, "_"), root);
  }

  /** Generate a confirmation dialog. */
  static confirm(
    message: string,
    opts?: {
      yes?: string;
      no?: string;
      yesAction?: string | Record<string, unknown>;
      noAction?: string | Record<string, unknown>;
    },
  ): UISurface {
    const root = UI.column([
      UI.text(message, { variant: "body" }),
      UI.row([
        UI.button(opts?.yes ?? "Yes", { variant: "primary", action: opts?.yesAction }),
        UI.button(opts?.no ?? "No", { variant: "default", action: opts?.noAction }),
      ]),
    ]);
    return new UISurface("confirm", root);
  }

  /** Generate a data table. */
  static table(
    columns: Array<string | { label: string; key: string }>,
    opts?: { dataBind?: string; id?: string },
  ): UIComponent {
    const normalizedColumns = columns.map((c) =>
      typeof c === "string" ? { label: c, key: c } : c,
    );
    return new UIComponent(
      "Table",
      {
        columns: normalizedColumns,
        dataBind: opts?.dataBind,
      },
      [],
      opts?.id,
    );
  }

  /** Generate a multi-step wizard. */
  static wizard(
    title: string,
    opts: { steps: Array<{ label: string; content: UIComponent }> },
  ): UISurface {
    const root = UI.column([UI.heading(title), new UIComponent("Wizard", { steps: opts.steps })]);
    return new UISurface(title.toLowerCase().replace(/\s+/g, "_"), root);
  }
}
