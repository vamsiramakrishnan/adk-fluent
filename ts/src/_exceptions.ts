/**
 * A2UI exception classes — mirror the Python wedge.
 *
 * Re-exported from the top-level package entry point.
 */

export class A2UIError extends Error {
  override name = "A2UIError";
}

export class A2UINotInstalled extends A2UIError {
  override name = "A2UINotInstalled";
}

export class A2UISurfaceError extends A2UIError {
  override name = "A2UISurfaceError";
  surfaceName?: string;

  constructor(message: string, surfaceName?: string) {
    super(surfaceName ? `[${surfaceName}] ${message}` : message);
    this.surfaceName = surfaceName;
  }
}

export class A2UIBindingError extends A2UISurfaceError {
  override name = "A2UIBindingError";
  path?: string;

  constructor(message: string, opts: { surfaceName?: string; path?: string } = {}) {
    super(message, opts.surfaceName);
    this.path = opts.path;
  }
}
