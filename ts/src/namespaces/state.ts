/**
 * S — State transform namespace.
 *
 * Factory methods returning composable state transforms.
 * Compose with .pipe() (chain) or .merge() (combine).
 *
 * Usage:
 *   S.pick("key1", "key2")        // keep only named keys
 *   S.rename({ old: "new" })      // rename keys
 *   S.default_({ x: 0 })          // fill missing keys
 *   S.pick("a").pipe(S.set({b:1})) // chain transforms
 */

import type { State, StateTransform } from "../core/types.js";

/** A composable state transform descriptor. */
export class STransform {
  constructor(
    public readonly name: string,
    public readonly fn: StateTransform,
    public readonly readsKeys: string[] | null = null,
    public readonly writesKeys: string[] | null = null,
  ) {}

  /** Chain: run this transform, then other on the result. */
  pipe(other: STransform): STransform {
    const self = this;
    return new STransform(`${self.name}>>${other.name}`, (state) => other.fn(self.fn(state)));
  }

  /** Combine: both read same input, merge outputs. */
  merge(other: STransform): STransform {
    const self = this;
    return new STransform(`${self.name}+${other.name}`, (state) => ({
      ...self.fn(state),
      ...other.fn(state),
    }));
  }

  /** Apply this transform to a state. */
  apply(state: State): State {
    return this.fn(state);
  }
}

/**
 * S namespace — state transform factories.
 *
 * All 24 methods from the Python S namespace are ported here.
 */
export class S {
  // ------------------------------------------------------------------
  // Key selection
  // ------------------------------------------------------------------

  /** Keep only the named keys. */
  static pick(...keys: string[]): STransform {
    return new STransform(
      `pick(${keys.join(",")})`,
      (state) => {
        const result: State = {};
        for (const k of keys) {
          if (k in state) result[k] = state[k];
        }
        return result;
      },
      keys,
    );
  }

  /** Remove the named keys. */
  static drop(...keys: string[]): STransform {
    const dropSet = new Set(keys);
    return new STransform(`drop(${keys.join(",")})`, (state) => {
      const result: State = {};
      for (const [k, v] of Object.entries(state)) {
        if (!dropSet.has(k)) result[k] = v;
      }
      return result;
    });
  }

  /** Rename keys: S.rename({ oldName: "newName" }). */
  static rename(mapping: Record<string, string>): STransform {
    return new STransform("rename", (state) => {
      const result: State = { ...state };
      for (const [oldKey, newKey] of Object.entries(mapping)) {
        if (oldKey in result) {
          result[newKey] = result[oldKey];
          delete result[oldKey];
        }
      }
      return result;
    });
  }

  // ------------------------------------------------------------------
  // Value transforms
  // ------------------------------------------------------------------

  /** Apply a function to transform one key's value. */
  static transform(key: string, fn: (value: unknown) => unknown): STransform {
    return new STransform(
      `transform(${key})`,
      (state) => ({
        ...state,
        [key]: fn(state[key]),
      }),
      [key],
      [key],
    );
  }

  /** Derive new keys from full state. */
  static compute(factories: Record<string, (state: State) => unknown>): STransform {
    return new STransform(
      "compute",
      (state) => {
        const result: State = { ...state };
        for (const [key, fn] of Object.entries(factories)) {
          result[key] = fn(state);
        }
        return result;
      },
      null,
      Object.keys(factories),
    );
  }

  /** Merge multiple keys into a single key. */
  static merge_(
    keys: string[],
    into: string,
    fn?: (values: Record<string, unknown>) => unknown,
  ): STransform {
    return new STransform(
      `merge(${keys.join(",")}→${into})`,
      (state) => {
        const collected: Record<string, unknown> = {};
        for (const k of keys) {
          if (k in state) collected[k] = state[k];
        }
        const merged = fn ? fn(collected) : collected;
        return { ...state, [into]: merged };
      },
      keys,
      [into],
    );
  }

  // ------------------------------------------------------------------
  // Setters
  // ------------------------------------------------------------------

  /** Set explicit key-value pairs. */
  static set(values: Record<string, unknown>): STransform {
    return new STransform("set", (state) => ({ ...state, ...values }), null, Object.keys(values));
  }

  /** Fill missing keys with defaults. */
  static default_(defaults: Record<string, unknown>): STransform {
    return new STransform("default", (state) => {
      const result: State = { ...state };
      for (const [k, v] of Object.entries(defaults)) {
        if (!(k in result)) result[k] = v;
      }
      return result;
    });
  }

  /** Capture user message into state[key]. */
  static capture(key: string): STransform {
    return new STransform(
      `capture(${key})`,
      (state) => {
        // At runtime, the ADK runner injects the user message
        return state;
      },
      null,
      [key],
    );
  }

  // ------------------------------------------------------------------
  // Accumulators
  // ------------------------------------------------------------------

  /** Append current value of key to a running list (default: same key). */
  static accumulate(key: string, into?: string): STransform {
    const target = into ?? key;
    return new STransform(
      `accumulate(${key}→${target})`,
      (state) => {
        const list = Array.isArray(state[target]) ? [...(state[target] as unknown[])] : [];
        if (key in state) list.push(state[key]);
        return { ...state, [target]: list };
      },
      [key],
      [target],
    );
  }

  /** Increment a numeric counter in state. */
  static counter(key: string, step = 1): STransform {
    return new STransform(
      `counter(${key})`,
      (state) => ({
        ...state,
        [key]: ((state[key] as number) ?? 0) + step,
      }),
      [key],
      [key],
    );
  }

  /** Maintain a rolling history of a key's values. */
  static history(key: string, maxSize = 10): STransform {
    const historyKey = `${key}_history`;
    return new STransform(
      `history(${key})`,
      (state) => {
        const hist = Array.isArray(state[historyKey]) ? [...(state[historyKey] as unknown[])] : [];
        if (key in state) hist.push(state[key]);
        while (hist.length > maxSize) hist.shift();
        return { ...state, [historyKey]: hist };
      },
      [key],
      [historyKey],
    );
  }

  // ------------------------------------------------------------------
  // Assertions
  // ------------------------------------------------------------------

  /** Assert a state invariant. Throws if predicate fails. */
  static guard(predicate: (state: State) => boolean, msg?: string): STransform {
    return new STransform("guard", (state) => {
      if (!predicate(state)) {
        throw new Error(msg ?? "State guard failed");
      }
      return state;
    });
  }

  /** Assert that all named keys exist and are truthy. */
  static require(...keys: string[]): STransform {
    return new STransform(
      `require(${keys.join(",")})`,
      (state) => {
        for (const k of keys) {
          if (!(k in state) || !state[k]) {
            throw new Error(`Required state key "${k}" is missing or falsy`);
          }
        }
        return state;
      },
      keys,
    );
  }

  /** Validate state against a schema (Zod or custom validator). */
  static validate(
    schemaOrValidator: { parse: (v: unknown) => unknown } | ((state: State) => boolean),
    _opts?: { strict?: boolean },
  ): STransform {
    return new STransform("validate", (state) => {
      if (typeof schemaOrValidator === "function") {
        if (!schemaOrValidator(state)) {
          throw new Error("State validation failed");
        }
      } else {
        schemaOrValidator.parse(state);
      }
      return state;
    });
  }

  // ------------------------------------------------------------------
  // Structural transforms
  // ------------------------------------------------------------------

  /** Flatten a nested dict to dotted keys: { a: { b: 1 } } → { "a.b": 1 }. */
  static flatten(key: string, separator = "."): STransform {
    return new STransform(
      `flatten(${key})`,
      (state) => {
        const nested = state[key];
        if (typeof nested !== "object" || nested === null) return state;
        const flat: State = {};
        const walk = (obj: Record<string, unknown>, prefix: string) => {
          for (const [k, v] of Object.entries(obj)) {
            const path = prefix ? `${prefix}${separator}${k}` : k;
            if (typeof v === "object" && v !== null && !Array.isArray(v)) {
              walk(v as Record<string, unknown>, path);
            } else {
              flat[path] = v;
            }
          }
        };
        walk(nested as Record<string, unknown>, "");
        return { ...state, [key]: flat };
      },
      [key],
      [key],
    );
  }

  /** Unflatten dotted keys to nested: { "a.b": 1 } → { a: { b: 1 } }. */
  static unflatten(key: string, separator = "."): STransform {
    return new STransform(
      `unflatten(${key})`,
      (state) => {
        const flat = state[key];
        if (typeof flat !== "object" || flat === null) return state;
        const nested: Record<string, unknown> = {};
        for (const [path, value] of Object.entries(flat as Record<string, unknown>)) {
          const parts = path.split(separator);
          let current: Record<string, unknown> = nested;
          for (let i = 0; i < parts.length - 1; i++) {
            if (!(parts[i] in current)) current[parts[i]] = {};
            current = current[parts[i]] as Record<string, unknown>;
          }
          current[parts[parts.length - 1]] = value;
        }
        return { ...state, [key]: nested };
      },
      [key],
      [key],
    );
  }

  /** Zip parallel lists: S.zip("names", "scores", into: "pairs"). */
  static zip(keys: string[], into: string): STransform {
    return new STransform(
      `zip(${keys.join(",")}→${into})`,
      (state) => {
        const arrays = keys.map((k) => (state[k] as unknown[]) ?? []);
        const maxLen = Math.max(...arrays.map((a) => a.length));
        const zipped: unknown[][] = [];
        for (let i = 0; i < maxLen; i++) {
          zipped.push(arrays.map((a) => a[i]));
        }
        return { ...state, [into]: zipped };
      },
      keys,
      [into],
    );
  }

  /** Group list items by a key function. */
  static groupBy(itemsKey: string, keyFn: (item: unknown) => string, into: string): STransform {
    return new STransform(
      `groupBy(${itemsKey}→${into})`,
      (state) => {
        const items = (state[itemsKey] as unknown[]) ?? [];
        const groups: Record<string, unknown[]> = {};
        for (const item of items) {
          const groupKey = keyFn(item);
          if (!groups[groupKey]) groups[groupKey] = [];
          groups[groupKey].push(item);
        }
        return { ...state, [into]: groups };
      },
      [itemsKey],
      [into],
    );
  }

  // ------------------------------------------------------------------
  // Control flow
  // ------------------------------------------------------------------

  /** Conditional transform: apply only if predicate is true. */
  static when(predicate: (state: State) => boolean, transform: STransform): STransform {
    return new STransform(`when(${transform.name})`, (state) =>
      predicate(state) ? transform.fn(state) : state,
    );
  }

  /** Route to different transforms based on a state key value. */
  static branch(
    key: string,
    routes: Record<string, STransform>,
    fallback?: STransform,
  ): STransform {
    return new STransform(
      `branch(${key})`,
      (state) => {
        const value = String(state[key] ?? "");
        const transform = routes[value] ?? fallback;
        return transform ? transform.fn(state) : state;
      },
      [key],
    );
  }

  // ------------------------------------------------------------------
  // Identity and debug
  // ------------------------------------------------------------------

  /** Pass-through (no-op). */
  static identity(): STransform {
    return new STransform("identity", (state) => state);
  }

  /** Log selected state keys to stderr. */
  static log(...keys: string[]): STransform {
    return new STransform(`log(${keys.join(",")})`, (state) => {
      const label = keys.length > 0 ? keys : Object.keys(state);
      for (const k of label) {
        console.error(`[S.log] ${k} =`, state[k]);
      }
      return state;
    });
  }

  // ------------------------------------------------------------------
  // A2UI bridge
  // ------------------------------------------------------------------

  /** Bridge state keys → A2UI data model. */
  static toUi(...keys: string[]): STransform {
    return new STransform(
      `toUi(${keys.join(",")})`,
      (state) => {
        // At runtime, this bridges to the A2UI surface data model
        return state;
      },
      keys,
    );
  }

  /** Bridge A2UI data model → state keys. */
  static fromUi(...keys: string[]): STransform {
    return new STransform(
      `fromUi(${keys.join(",")})`,
      (state) => {
        return state;
      },
      null,
      keys,
    );
  }
}
