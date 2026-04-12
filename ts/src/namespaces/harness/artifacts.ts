/**
 * Artifact store for large outputs and blobs. Mirrors `_harness/_artifacts.py`.
 */

import {
  existsSync,
  mkdirSync,
  readFileSync,
  readdirSync,
  unlinkSync,
  writeFileSync,
} from "node:fs";
import { join } from "node:path";

export interface ArtifactStoreOptions {
  maxInlineBytes?: number;
}

export class ArtifactStore {
  readonly path: string;
  readonly maxInlineBytes: number;

  constructor(path: string, opts: ArtifactStoreOptions = {}) {
    this.path = path;
    this.maxInlineBytes = opts.maxInlineBytes ?? 10_000;
    mkdirSync(this.path, { recursive: true });
  }

  /** Save text content. Returns "inline" or the artifact filename. */
  save(filename: string, content: string): { filename: string; inline: boolean } {
    if (Buffer.byteLength(content, "utf8") <= this.maxInlineBytes) {
      return { filename, inline: true };
    }
    writeFileSync(join(this.path, filename), content, "utf8");
    return { filename, inline: false };
  }

  saveBinary(filename: string, bytes: Uint8Array): { filename: string; inline: boolean } {
    if (bytes.byteLength <= this.maxInlineBytes) {
      return { filename, inline: true };
    }
    writeFileSync(join(this.path, filename), bytes);
    return { filename, inline: false };
  }

  load(filename: string): string {
    return readFileSync(join(this.path, filename), "utf8");
  }

  loadBinary(filename: string): Buffer {
    return readFileSync(join(this.path, filename));
  }

  list(): string[] {
    if (!existsSync(this.path)) return [];
    return readdirSync(this.path).sort();
  }

  delete(filename: string): boolean {
    const p = join(this.path, filename);
    if (!existsSync(p)) return false;
    unlinkSync(p);
    return true;
  }
}
