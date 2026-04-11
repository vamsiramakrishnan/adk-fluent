/**
 * S — State transform namespace.
 *
 * Factory methods returning composable state transforms.
 * Use with Pipeline steps or the >> operator equivalent.
 *
 * Usage:
 *   S.pick("key1", "key2")    // keep only named keys
 *   S.rename({ old: "new" })  // rename keys
 *   S.default({ x: 0 })      // fill missing keys with defaults
 */

import type { State, StateTransform } from "../core/types.js";

/** A composable state transform descriptor. */
export class STransform {
  constructor(
    public readonly name: string,
    public readonly fn: StateTransform,
  ) {}

  /** Chain two transforms: first this, then other. */
  pipe(other: STransform): STransform {
    const self = this;
    return new STransform(`${self.name}_then_${other.name}`, (state) =>
      other.fn(self.fn(state)),
    );
  }

  /** Combine two transforms (both read same state, merge results). */
  merge(other: STransform): STransform {
    const self = this;
    return new STransform(`${self.name}_and_${other.name}`, (state) => ({
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
 */
export class S {
  /** Keep only the named keys. */
  static pick(...keys: string[]): STransform {
    return new STransform(`pick(${keys.join(",")})`, (state) => {
      const result: State = {};
      for (const k of keys) {
        if (k in state) result[k] = state[k];
      }
      return result;
    });
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

  /** Rename keys according to the mapping. */
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

  /** Merge multiple keys into one. */
  static mergeKeys(...keys: string[]): (into: string) => STransform {
    return (into: string) =>
      new STransform(`merge(${keys.join(",")}→${into})`, (state) => {
        const merged: Record<string, unknown> = {};
        for (const k of keys) {
          if (k in state) merged[k] = state[k];
        }
        return { ...state, [into]: merged };
      });
  }

  /** Apply a function to transform one key's value. */
  static transform(key: string, fn: (value: unknown) => unknown): STransform {
    return new STransform(`transform(${key})`, (state) => ({
      ...state,
      [key]: fn(state[key]),
    }));
  }

  /** Derive new keys from state. */
  static compute(factories: Record<string, (state: State) => unknown>): STransform {
    return new STransform("compute", (state) => {
      const result: State = { ...state };
      for (const [key, fn] of Object.entries(factories)) {
        result[key] = fn(state);
      }
      return result;
    });
  }

  /** Set explicit key-value pairs. */
  static set(values: Record<string, unknown>): STransform {
    return new STransform("set", (state) => ({ ...state, ...values }));
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

  /** Assert a state invariant. Throws if predicate fails. */
  static guard(
    predicate: (state: State) => boolean,
    msg?: string,
  ): STransform {
    return new STransform("guard", (state) => {
      if (!predicate(state)) {
        throw new Error(msg ?? "State guard failed");
      }
      return state;
    });
  }

  /** Conditional transform: apply only if predicate is true. */
  static when(
    predicate: (state: State) => boolean,
    transform: STransform,
  ): STransform {
    return new STransform(`when(${transform.name})`, (state) =>
      predicate(state) ? transform.fn(state) : state,
    );
  }

  /** Assert that all named keys exist in state. */
  static require(...keys: string[]): STransform {
    return new STransform(`require(${keys.join(",")})`, (state) => {
      for (const k of keys) {
        if (!(k in state)) {
          throw new Error(`Required state key "${k}" is missing`);
        }
      }
      return state;
    });
  }

  /** Pass-through (no-op). */
  static identity(): STransform {
    return new STransform("identity", (state) => state);
  }

  /** Log state keys to console. */
  static log(...keys: string[]): STransform {
    return new STransform(`log(${keys.join(",")})`, (state) => {
      for (const k of keys) {
        console.error(`[S.log] ${k} =`, state[k]);
      }
      return state;
    });
  }
}
