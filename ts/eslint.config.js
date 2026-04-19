// ─────────────────────────────────────────────────────────────────────────────
// adk-fluent-ts ESLint flat config (ESLint 9+).
//
// Mirrors the discipline of python/pyproject.toml's ruff config:
//   • Strict TypeScript rules where they catch real bugs
//   • Generated builders (src/builders/*.ts) are owned by the codegen pipeline
//     and exempted from style enforcement — only soundness rules apply
//   • Tests get a slightly looser ruleset (any, non-null assertions)
//
// Run:
//   npm run lint           # report only
//   npm run lint:fix       # auto-fix
// ─────────────────────────────────────────────────────────────────────────────

import js from "@eslint/js";
import tseslint from "@typescript-eslint/eslint-plugin";
import tsparser from "@typescript-eslint/parser";
import prettier from "eslint-config-prettier";

// Node + DOM globals available in our runtime targets.
// adk-fluent-ts runs in Node 20+ for production but is also embeddable in
// edge/browser runtimes that ship the same Web APIs (TextDecoder, etc.).
const globals = {
  console: "readonly",
  process: "readonly",
  Buffer: "readonly",
  setTimeout: "readonly",
  clearTimeout: "readonly",
  setInterval: "readonly",
  clearInterval: "readonly",
  setImmediate: "readonly",
  clearImmediate: "readonly",
  globalThis: "readonly",
  TextDecoder: "readonly",
  TextEncoder: "readonly",
  URL: "readonly",
  URLSearchParams: "readonly",
  fetch: "readonly",
  Request: "readonly",
  Response: "readonly",
  Headers: "readonly",
  AbortController: "readonly",
  AbortSignal: "readonly",
  structuredClone: "readonly",
  __dirname: "readonly",
  __filename: "readonly",
  module: "readonly",
  require: "readonly",
};

export default [
  // ─── ignore patterns (mirrors .prettierignore) ─────────────────────────────
  {
    ignores: [
      "dist/**",
      "docs/api/**",
      "node_modules/**",
      "coverage/**",
      "*.config.js",
      "*.config.mjs",
      "*.config.ts", // vitest.config.ts — Vite handles its own typecheck
      "eslint.config.js",
    ],
  },

  // ─── base JS recommended ───────────────────────────────────────────────────
  js.configs.recommended,

  // ─── TypeScript source files ───────────────────────────────────────────────
  {
    files: ["src/**/*.ts", "src/**/*.tsx"],
    languageOptions: {
      parser: tsparser,
      parserOptions: {
        ecmaVersion: 2022,
        sourceType: "module",
      },
      globals,
    },
    plugins: {
      "@typescript-eslint": tseslint,
    },
    rules: {
      ...tseslint.configs.recommended.rules,

      // Soundness — keep these strict
      "@typescript-eslint/no-floating-promises": "off", // requires type-info project
      "@typescript-eslint/no-explicit-any": "warn",
      "@typescript-eslint/no-this-alias": "off",
      "@typescript-eslint/no-unsafe-function-type": "warn",
      "@typescript-eslint/no-unused-vars": [
        "error",
        {
          argsIgnorePattern: "^_",
          varsIgnorePattern: "^_",
          caughtErrorsIgnorePattern: "^_",
        },
      ],
      "@typescript-eslint/consistent-type-imports": [
        "error",
        { prefer: "type-imports", fixStyle: "inline-type-imports" },
      ],
      "@typescript-eslint/no-non-null-assertion": "warn",

      // Style — defer to Prettier
      "no-unused-vars": "off", // handled by @typescript-eslint version
      "no-empty": ["error", { allowEmptyCatch: true }],
      "prefer-const": "error",
      "no-var": "error",
      eqeqeq: ["error", "always", { null: "ignore" }],
    },
  },

  // ─── flux React renderer: needs DOM globals for style injection ───────────
  // Runs in the browser; theme.ts uses document / HTMLStyleElement to inject
  // the CSS-var <style> block at mount.
  {
    files: ["src/flux/renderer/**/*.ts", "src/flux/renderer/**/*.tsx"],
    languageOptions: {
      parser: tsparser,
      parserOptions: {
        ecmaVersion: 2022,
        sourceType: "module",
        ecmaFeatures: { jsx: true },
      },
      globals: {
        ...globals,
        document: "readonly",
        window: "readonly",
        HTMLElement: "readonly",
        HTMLStyleElement: "readonly",
        HTMLInputElement: "readonly",
        HTMLButtonElement: "readonly",
        HTMLAnchorElement: "readonly",
      },
    },
    plugins: { "@typescript-eslint": tseslint },
    rules: {
      ...tseslint.configs.recommended.rules,
      "@typescript-eslint/no-non-null-assertion": "off",
      "@typescript-eslint/no-explicit-any": "warn",
      "@typescript-eslint/consistent-type-imports": [
        "error",
        { prefer: "type-imports", fixStyle: "inline-type-imports" },
      ],
    },
  },

  // ─── generated builders: only soundness, no style ──────────────────────────
  // These files are owned by `just ts-generate` (shared/scripts/code_ir).
  // Lint must not block CI on stylistic choices baked into the emitter —
  // only flag genuine soundness errors (typescript-eslint already handles via tsc).
  {
    files: ["src/builders/**/*.ts"],
    languageOptions: {
      parser: tsparser,
      parserOptions: { ecmaVersion: 2022, sourceType: "module" },
      globals,
    },
    plugins: { "@typescript-eslint": tseslint },
    rules: {
      "@typescript-eslint/no-explicit-any": "off",
      "@typescript-eslint/no-unused-vars": "off",
      "@typescript-eslint/no-non-null-assertion": "off",
      "@typescript-eslint/consistent-type-imports": "off",
      "@typescript-eslint/no-this-alias": "off",
      "@typescript-eslint/no-unsafe-function-type": "off",
      "@typescript-eslint/no-empty-object-type": "off",
      "no-empty": "off",
      "no-undef": "off",
      "no-unused-vars": "off",
    },
  },

  // ─── tests: looser ─────────────────────────────────────────────────────────
  {
    files: ["tests/**/*.ts", "**/*.test.ts", "**/*.spec.ts"],
    languageOptions: {
      parser: tsparser,
      parserOptions: {
        ecmaVersion: 2022,
        sourceType: "module",
      },
      globals,
    },
    plugins: {
      "@typescript-eslint": tseslint,
    },
    rules: {
      ...tseslint.configs.recommended.rules,
      "@typescript-eslint/no-explicit-any": "off",
      "@typescript-eslint/no-non-null-assertion": "off",
      "@typescript-eslint/no-unused-vars": [
        "warn",
        { argsIgnorePattern: "^_", varsIgnorePattern: "^_" },
      ],
    },
  },

  // ─── prettier: must come LAST so it disables conflicting style rules ───────
  prettier,
];
