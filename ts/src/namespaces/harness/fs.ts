/**
 * Pluggable filesystem backend.
 *
 * Mirrors `python/src/adk_fluent/_fs/`. Workspace tools route every I/O
 * call through a `FsBackend` so they can be unit-tested without a real
 * disk and re-targeted at in-memory or remote storage without touching
 * the tool code.
 *
 * Three concrete backends:
 * - `LocalBackend` — real on-disk I/O via Node's `fs` module.
 * - `MemoryBackend` — dict-backed fake for tests and ephemeral
 *   scratch workspaces. POSIX semantics regardless of host OS.
 * - `SandboxedBackend` — decorator wrapping any backend with a
 *   `SandboxPolicy`; refuses operations that would escape the
 *   workspace.
 */

import * as fs from "node:fs";
import * as path from "node:path";

import type { SandboxPolicy } from "./sandbox.js";

/**
 * Node's `BufferEncoding` is a global type supplied by `@types/node`.
 * We re-declare it locally so `eslint`'s `no-undef` rule (which does not
 * know about ambient global types) stays quiet without sacrificing the
 * strongly-typed surface.
 */
type BufferEncoding =
  | "ascii"
  | "utf8"
  | "utf-8"
  | "utf16le"
  | "utf-16le"
  | "ucs2"
  | "ucs-2"
  | "base64"
  | "base64url"
  | "latin1"
  | "binary"
  | "hex";

/** Minimal stat result returned by `FsBackend.stat()`. */
export interface FsStat {
  path: string;
  size: number;
  isDir: boolean;
  isFile: boolean;
  /** Modification time in milliseconds since epoch. */
  mtime: number;
}

/** One entry produced by `FsBackend.listDir()`. */
export interface FsEntry {
  name: string;
  path: string;
  isDir: boolean;
  isFile: boolean;
}

/**
 * The subset of filesystem operations workspace tools need.
 *
 * A backend that wants to expose extras (random-access seeks, chunked
 * reads, partial writes) is free to do so through subclass-specific
 * methods, but the tools themselves never reach for anything outside
 * this interface.
 */
export interface FsBackend {
  exists(path: string): boolean;
  stat(path: string): FsStat;
  readText(path: string, options?: { encoding?: BufferEncoding }): string;
  readBytes(path: string): Uint8Array;
  writeText(path: string, content: string, options?: { encoding?: BufferEncoding }): void;
  writeBytes(path: string, content: Uint8Array): void;
  delete_(path: string): void;
  mkdir(path: string, options?: { parents?: boolean; existOk?: boolean }): void;
  listDir(path: string): FsEntry[];
  iterFiles(root: string): IterableIterator<string>;
  glob(pattern: string, options?: { root?: string }): string[];
}

/**
 * `FsBackend` backed by Node's real filesystem via `node:fs`.
 *
 * This backend does **no** sandboxing. Wrap it with
 * `SandboxedBackend` to enforce a workspace scope.
 */
export class LocalBackend implements FsBackend {
  private readonly root: string | undefined;

  constructor(root?: string) {
    this.root = root;
  }

  private resolve(target: string): string {
    if (this.root && !path.isAbsolute(target)) {
      return path.join(this.root, target);
    }
    return target;
  }

  exists(target: string): boolean {
    return fs.existsSync(this.resolve(target));
  }

  stat(target: string): FsStat {
    const resolved = this.resolve(target);
    const st = fs.statSync(resolved);
    return {
      path: resolved,
      size: st.size,
      isDir: st.isDirectory(),
      isFile: st.isFile(),
      mtime: st.mtimeMs,
    };
  }

  readText(target: string, options: { encoding?: BufferEncoding } = {}): string {
    const encoding = options.encoding ?? "utf-8";
    return fs.readFileSync(this.resolve(target), { encoding });
  }

  readBytes(target: string): Uint8Array {
    return new Uint8Array(fs.readFileSync(this.resolve(target)));
  }

  writeText(target: string, content: string, options: { encoding?: BufferEncoding } = {}): void {
    const encoding = options.encoding ?? "utf-8";
    const resolved = this.resolve(target);
    fs.mkdirSync(path.dirname(resolved), { recursive: true });
    fs.writeFileSync(resolved, content, { encoding });
  }

  writeBytes(target: string, content: Uint8Array): void {
    const resolved = this.resolve(target);
    fs.mkdirSync(path.dirname(resolved), { recursive: true });
    fs.writeFileSync(resolved, content);
  }

  delete_(target: string): void {
    const resolved = this.resolve(target);
    const st = fs.statSync(resolved);
    if (st.isDirectory()) {
      // Mirror Python: only allow empty-dir removal. Recursive delete
      // belongs in a dedicated helper.
      fs.rmdirSync(resolved);
    } else {
      fs.unlinkSync(resolved);
    }
  }

  mkdir(target: string, options: { parents?: boolean; existOk?: boolean } = {}): void {
    const resolved = this.resolve(target);
    const parents = options.parents ?? true;
    const existOk = options.existOk ?? true;
    try {
      fs.mkdirSync(resolved, { recursive: parents });
    } catch (exc: unknown) {
      const err = exc as { code?: string };
      if (err.code === "EEXIST" && existOk) return;
      throw exc;
    }
  }

  listDir(target: string): FsEntry[] {
    const resolved = this.resolve(target);
    const entries = fs.readdirSync(resolved, { withFileTypes: true });
    entries.sort((a, b) => a.name.localeCompare(b.name));
    return entries.map((entry) => ({
      name: entry.name,
      path: path.join(resolved, entry.name),
      isDir: entry.isDirectory(),
      isFile: entry.isFile(),
    }));
  }

  *iterFiles(root: string): IterableIterator<string> {
    const resolved = this.resolve(root);
    const stack: string[] = [resolved];
    while (stack.length > 0) {
      const current = stack.pop();
      if (current === undefined) break;
      let entries: fs.Dirent[];
      try {
        entries = fs.readdirSync(current, { withFileTypes: true });
      } catch {
        continue;
      }
      for (const entry of entries) {
        const child = path.join(current, entry.name);
        if (entry.isDirectory()) {
          stack.push(child);
        } else if (entry.isFile()) {
          yield child;
        }
      }
    }
  }

  glob(pattern: string, options: { root?: string } = {}): string[] {
    const base = options.root !== undefined ? this.resolve(options.root) : (this.root ?? ".");
    // Lightweight glob that supports `*`, `?`, and `**`. Matches
    // Python's `pathlib.Path.glob()` for the patterns the harness
    // actually uses.
    const matches: string[] = [];
    for (const file of this.iterFiles(base)) {
      const rel = path.relative(base, file);
      if (matchGlob(pattern, rel)) {
        matches.push(file);
      }
    }
    return matches.sort();
  }
}

/**
 * In-memory `FsBackend` for tests and ephemeral workspaces.
 *
 * Files are stored as `Uint8Array` in an internal map keyed by
 * normalised POSIX-style absolute path. Directories are tracked
 * separately so `listDir` can distinguish "empty dir" from "no such
 * dir". Internal semantics are POSIX regardless of host OS so tests
 * are portable across Linux/Mac/Windows.
 */
export class MemoryBackend implements FsBackend {
  private readonly files: Map<string, Uint8Array> = new Map();
  private readonly dirs: Set<string> = new Set(["/"]);
  private readonly mtimes: Map<string, number> = new Map();

  constructor(files?: Record<string, string | Uint8Array>) {
    if (files) {
      for (const [p, content] of Object.entries(files)) {
        if (typeof content === "string") {
          this.writeText(p, content);
        } else {
          this.writeBytes(p, content);
        }
      }
    }
  }

  private static norm(p: string): string {
    let out = p;
    if (!out.startsWith("/")) out = "/" + out;
    const parts: string[] = [];
    for (const seg of out.split("/")) {
      if (seg === "" || seg === ".") continue;
      if (seg === "..") {
        parts.pop();
        continue;
      }
      parts.push(seg);
    }
    return parts.length === 0 ? "/" : "/" + parts.join("/");
  }

  exists(target: string): boolean {
    const p = MemoryBackend.norm(target);
    return this.files.has(p) || this.dirs.has(p);
  }

  stat(target: string): FsStat {
    const p = MemoryBackend.norm(target);
    const file = this.files.get(p);
    if (file !== undefined) {
      return {
        path: p,
        size: file.byteLength,
        isDir: false,
        isFile: true,
        mtime: this.mtimes.get(p) ?? 0,
      };
    }
    if (this.dirs.has(p)) {
      return {
        path: p,
        size: 0,
        isDir: true,
        isFile: false,
        mtime: this.mtimes.get(p) ?? 0,
      };
    }
    throw Object.assign(new Error(`ENOENT: no such file or directory, '${target}'`), {
      code: "ENOENT",
    });
  }

  readText(target: string, options: { encoding?: BufferEncoding } = {}): string {
    const bytes = this.readBytes(target);
    const encoding = options.encoding ?? "utf-8";
    return Buffer.from(bytes).toString(encoding);
  }

  readBytes(target: string): Uint8Array {
    const p = MemoryBackend.norm(target);
    const file = this.files.get(p);
    if (file === undefined) {
      throw Object.assign(new Error(`ENOENT: no such file or directory, '${target}'`), {
        code: "ENOENT",
      });
    }
    return new Uint8Array(file);
  }

  writeText(target: string, content: string, options: { encoding?: BufferEncoding } = {}): void {
    const encoding = options.encoding ?? "utf-8";
    this.writeBytes(target, new Uint8Array(Buffer.from(content, encoding)));
  }

  writeBytes(target: string, content: Uint8Array): void {
    const p = MemoryBackend.norm(target);
    // Ensure parent directories exist.
    let parent = posixDirname(p);
    while (parent && !this.dirs.has(parent)) {
      this.dirs.add(parent);
      parent = posixDirname(parent);
    }
    this.files.set(p, new Uint8Array(content));
    this.mtimes.set(p, Date.now());
  }

  delete_(target: string): void {
    const p = MemoryBackend.norm(target);
    if (this.files.has(p)) {
      this.files.delete(p);
      this.mtimes.delete(p);
      return;
    }
    if (this.dirs.has(p)) {
      for (const f of this.files.keys()) {
        if (f.startsWith(p + "/")) {
          throw new Error(`Directory not empty: ${target}`);
        }
      }
      for (const d of this.dirs) {
        if (d.startsWith(p + "/")) {
          throw new Error(`Directory not empty: ${target}`);
        }
      }
      this.dirs.delete(p);
      return;
    }
    throw Object.assign(new Error(`ENOENT: no such file or directory, '${target}'`), {
      code: "ENOENT",
    });
  }

  mkdir(target: string, options: { parents?: boolean; existOk?: boolean } = {}): void {
    const parents = options.parents ?? true;
    const existOk = options.existOk ?? true;
    const p = MemoryBackend.norm(target);
    if (this.dirs.has(p)) {
      if (!existOk) throw new Error(`FileExists: ${target}`);
      return;
    }
    if (!parents && !this.dirs.has(posixDirname(p))) {
      throw Object.assign(new Error(`ENOENT: parent missing for '${target}'`), { code: "ENOENT" });
    }
    let cursor = "";
    for (const seg of p.split("/").filter(Boolean)) {
      cursor = cursor + "/" + seg;
      this.dirs.add(cursor);
      if (!this.mtimes.has(cursor)) this.mtimes.set(cursor, Date.now());
    }
  }

  listDir(target: string): FsEntry[] {
    const p = MemoryBackend.norm(target);
    if (!this.dirs.has(p)) {
      throw Object.assign(new Error(`ENOENT: no such directory, '${target}'`), { code: "ENOENT" });
    }
    const prefix = p === "/" ? "/" : p + "/";
    const entries: FsEntry[] = [];
    const seenDirs = new Set<string>();

    for (const f of this.files.keys()) {
      if (!f.startsWith(prefix)) continue;
      const rest = f.slice(prefix.length);
      if (!rest.includes("/")) {
        entries.push({ name: rest, path: f, isDir: false, isFile: true });
      } else {
        seenDirs.add(rest.split("/", 1)[0]);
      }
    }
    for (const d of this.dirs) {
      if (!d.startsWith(prefix)) continue;
      const rest = d.slice(prefix.length);
      if (rest && !rest.includes("/")) seenDirs.add(rest);
    }
    for (const name of [...seenDirs].sort()) {
      entries.push({
        name,
        path: p === "/" ? "/" + name : p + "/" + name,
        isDir: true,
        isFile: false,
      });
    }
    entries.sort((a, b) => {
      if (a.isDir !== b.isDir) return a.isDir ? -1 : 1;
      return a.name.localeCompare(b.name);
    });
    return entries;
  }

  *iterFiles(root: string): IterableIterator<string> {
    const r = MemoryBackend.norm(root);
    const prefix = r === "/" ? "/" : r + "/";
    const sorted = [...this.files.keys()].sort();
    for (const f of sorted) {
      if (r === "/" ? f.startsWith("/") : f.startsWith(prefix)) {
        yield f;
      }
    }
  }

  glob(pattern: string, options: { root?: string } = {}): string[] {
    const r = options.root !== undefined ? MemoryBackend.norm(options.root) : "/";
    const prefix = r === "/" ? "/" : r + "/";
    const matches: string[] = [];
    const sorted = [...this.files.keys()].sort();
    for (const f of sorted) {
      if (r !== "/" && !f.startsWith(prefix)) continue;
      const rel = r === "/" ? f.replace(/^\//, "") : f.slice(prefix.length);
      if (matchGlob(pattern, rel)) matches.push(f);
    }
    return matches;
  }
}

/**
 * Raised when a `SandboxedBackend` refuses an operation that would
 * escape the allowed workspace.
 */
export class SandboxViolation extends Error {
  constructor(message: string) {
    super(message);
    this.name = "SandboxViolation";
  }
}

/**
 * Decorator wrapping any `FsBackend` with a `SandboxPolicy`.
 *
 * Every operation resolves its path through the policy and refuses
 * the call if the resolved path escapes the workspace. Read and write
 * operations route through `checkRead` / `checkWrite` respectively so
 * extra read/write paths supplied to the policy apply uniformly.
 */
export class SandboxedBackend implements FsBackend {
  private readonly innerBackend: FsBackend;
  private readonly sandboxPolicy: SandboxPolicy;

  constructor(inner: FsBackend, sandbox: SandboxPolicy) {
    this.innerBackend = inner;
    this.sandboxPolicy = sandbox;
  }

  get sandbox(): SandboxPolicy {
    return this.sandboxPolicy;
  }

  get inner(): FsBackend {
    return this.innerBackend;
  }

  private checkRead(target: string): string {
    try {
      return this.sandboxPolicy.checkRead(target);
    } catch (exc) {
      const reason = exc instanceof Error ? exc.message : String(exc);
      throw new SandboxViolation(reason);
    }
  }

  private checkWrite(target: string): string {
    try {
      return this.sandboxPolicy.checkWrite(target);
    } catch (exc) {
      const reason = exc instanceof Error ? exc.message : String(exc);
      throw new SandboxViolation(reason);
    }
  }

  exists(target: string): boolean {
    try {
      const resolved = this.checkRead(target);
      return this.innerBackend.exists(resolved);
    } catch (exc) {
      if (exc instanceof SandboxViolation) return false;
      throw exc;
    }
  }

  stat(target: string): FsStat {
    return this.innerBackend.stat(this.checkRead(target));
  }

  readText(target: string, options?: { encoding?: BufferEncoding }): string {
    return this.innerBackend.readText(this.checkRead(target), options);
  }

  readBytes(target: string): Uint8Array {
    return this.innerBackend.readBytes(this.checkRead(target));
  }

  writeText(target: string, content: string, options?: { encoding?: BufferEncoding }): void {
    this.innerBackend.writeText(this.checkWrite(target), content, options);
  }

  writeBytes(target: string, content: Uint8Array): void {
    this.innerBackend.writeBytes(this.checkWrite(target), content);
  }

  delete_(target: string): void {
    this.innerBackend.delete_(this.checkWrite(target));
  }

  mkdir(target: string, options?: { parents?: boolean; existOk?: boolean }): void {
    this.innerBackend.mkdir(this.checkWrite(target), options);
  }

  listDir(target: string): FsEntry[] {
    return this.innerBackend.listDir(this.checkRead(target));
  }

  *iterFiles(root: string): IterableIterator<string> {
    yield* this.innerBackend.iterFiles(this.checkRead(root));
  }

  glob(pattern: string, options: { root?: string } = {}): string[] {
    const resolved =
      options.root !== undefined
        ? this.checkRead(options.root)
        : (this.sandboxPolicy.workspace ?? undefined);
    return this.innerBackend.glob(pattern, { root: resolved });
  }
}

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

function posixDirname(p: string): string {
  const idx = p.lastIndexOf("/");
  if (idx <= 0) return "/";
  return p.slice(0, idx);
}

/**
 * Match `target` against a glob `pattern` with `*`, `?`, and `**`
 * support. Used by `LocalBackend.glob()` and `MemoryBackend.glob()`
 * so both backends honour the same patterns.
 */
function matchGlob(pattern: string, target: string): boolean {
  const patParts = pattern.split("/");
  const pathParts = target ? target.split("/") : [""];

  const matchHere = (pi: number, xi: number): boolean => {
    while (pi < patParts.length) {
      const part = patParts[pi];
      if (part === "**") {
        if (pi + 1 === patParts.length) return true;
        for (let k = xi; k <= pathParts.length; k++) {
          if (matchHere(pi + 1, k)) return true;
        }
        return false;
      }
      if (xi >= pathParts.length) return false;
      if (!fnmatchCase(pathParts[xi], part)) return false;
      pi += 1;
      xi += 1;
    }
    return xi === pathParts.length;
  };

  return matchHere(0, 0);
}

function fnmatchCase(name: string, pattern: string): boolean {
  // Convert fnmatch pattern to a regex. Supports `*`, `?`, `[abc]`.
  let rx = "^";
  let i = 0;
  while (i < pattern.length) {
    const ch = pattern[i];
    if (ch === "*") rx += ".*";
    else if (ch === "?") rx += ".";
    else if (ch === "[") {
      const end = pattern.indexOf("]", i + 1);
      if (end === -1) {
        rx += "\\[";
      } else {
        rx += "[" + pattern.slice(i + 1, end) + "]";
        i = end;
      }
    } else if ("\\^$.+(){}|".includes(ch)) {
      rx += "\\" + ch;
    } else {
      rx += ch;
    }
    i += 1;
  }
  rx += "$";
  return new RegExp(rx).test(name);
}
