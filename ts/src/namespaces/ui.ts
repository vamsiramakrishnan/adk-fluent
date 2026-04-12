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

/** A named UI surface (compilation root). */
export class UISurface {
  constructor(
    public readonly name: string,
    public readonly root: UIComponent,
    public readonly meta: Record<string, unknown> = {},
  ) {}
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

  /** Create a named UI surface (compilation root). */
  static surface(name: string, root: UIComponent, meta?: Record<string, unknown>): UISurface {
    return new UISurface(name, root, meta);
  }

  /** Catalog-agnostic component factory (escape hatch). */
  static component(kind: string, opts?: { id?: string; [key: string]: unknown }): UIComponent {
    const { id, ...props } = opts ?? {};
    return new UIComponent(kind, props, [], id);
  }

  // ------------------------------------------------------------------
  // LLM-guided mode
  // ------------------------------------------------------------------

  /** LLM-guided mode: inject catalog schema so agent decides UI. */
  static auto(opts?: { catalog?: string }): Record<string, unknown> {
    return { type: "a2ui_auto", catalog: opts?.catalog ?? "basic" };
  }

  /** Schema-only prompt injection (no auto mode). */
  static schema(catalogUri?: string): Record<string, unknown> {
    return { type: "a2ui_schema", catalogUri: catalogUri ?? "basic" };
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

  /** Card container. */
  static card(child: UIComponent, opts?: { id?: string }): UIComponent {
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

  /** Button component. */
  static button(
    label: string,
    opts?: {
      variant?: "default" | "primary" | "borderless";
      action?: string | Record<string, unknown>;
      checks?: UICheck[];
      id?: string;
    },
  ): UIComponent {
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

  /** Text input field. */
  static textField(
    label: string,
    opts?: {
      value?: string;
      variant?: "shortText" | "longText" | "number" | "obscured";
      bind?: UIBinding;
      checks?: UICheck[];
      id?: string;
    },
  ): UIComponent {
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

  /** Generate a form surface from field spec. */
  static form(
    title: string,
    opts: {
      fields: Array<{ label: string; bind?: string; type?: string; required?: boolean }>;
      submit?: string;
      submitAction?: string | Record<string, unknown>;
    },
  ): UISurface {
    const fieldComponents = opts.fields.map((f) => {
      const checks: UICheck[] = [];
      if (f.required) checks.push(UI.required());
      return UI.textField(f.label, {
        variant: (f.type ?? "shortText") as "shortText" | "longText",
        bind: f.bind ? UI.bind(f.bind) : undefined,
        checks: checks.length > 0 ? checks : undefined,
      });
    });
    const submitBtn = UI.button(opts.submit ?? "Submit", {
      variant: "primary",
      action: opts.submitAction,
    });
    const root = UI.column([UI.heading(title), ...fieldComponents, submitBtn]);
    return new UISurface(title.toLowerCase().replace(/\s+/g, "_"), root);
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
