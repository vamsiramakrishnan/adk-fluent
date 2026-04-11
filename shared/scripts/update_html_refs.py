#!/usr/bin/env python3
"""Update standalone HTML reference pages for theme coherence and navigation.

Adds:
- Light/dark theme support (matching Furo docs theme)
- Sticky navigation bar with back-to-docs links
- Theme toggle button (auto-detects OS preference)
- Consistent footer with doc navigation
- prefers-color-scheme media query support
"""

import re
from pathlib import Path

DOCS_DIR = Path(__file__).resolve().parent.parent / "docs" / "user-guide"

# Map of filename -> (back_link_text, back_link_path, related_guide_page)
FILE_META = {
    "data-flow-reference.html": (
        "Data Flow",
        "user-guide/data-flow.html",
        "data-flow.html",
    ),
    "operator-algebra-reference.html": (
        "Expression Language",
        "user-guide/expression-language.html",
        "expression-language.html",
    ),
    "pcs-visual-reference.html": (
        "User Guide",
        "user-guide/index.html",
        "index.html",
    ),
    "module-lifecycle-reference.html": (
        "User Guide",
        "user-guide/index.html",
        "index.html",
    ),
    "delegation-reference.html": (
        "Transfer Control",
        "user-guide/transfer-control.html",
        "transfer-control.html",
    ),
    "execution-modes-reference.html": (
        "Execution",
        "user-guide/execution.html",
        "execution.html",
    ),
    "a2a-topology-reference.html": (
        "User Guide",
        "user-guide/index.html",
        "index.html",
    ),
}

# Navigation bar CSS + HTML (injected right after <body>)
NAV_CSS = """\

  /* ── Navigation bar ─────────────────────────────────────── */
  .ref-nav {
    position: sticky;
    top: 0;
    z-index: 1000;
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0.5rem 1.5rem;
    background: var(--nav-bg);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    border-bottom: 1px solid var(--border);
    font-family: var(--sans);
    font-size: 0.8rem;
  }

  .ref-nav-left {
    display: flex;
    align-items: center;
    gap: 0.75rem;
  }

  .ref-nav-logo {
    font-weight: 700;
    color: var(--brand);
    text-decoration: none;
    font-size: 0.85rem;
    letter-spacing: -0.01em;
  }

  .ref-nav-logo:hover { opacity: 0.8; }

  .ref-nav-sep {
    color: var(--text-dim);
    user-select: none;
  }

  .ref-nav-back {
    color: var(--text-dim);
    text-decoration: none;
    transition: color 0.15s;
  }

  .ref-nav-back:hover { color: var(--brand); }

  .ref-nav-right {
    display: flex;
    align-items: center;
    gap: 0.75rem;
  }

  .ref-nav-link {
    color: var(--text-dim);
    text-decoration: none;
    transition: color 0.15s;
  }

  .ref-nav-link:hover { color: var(--text); }

  .theme-toggle {
    background: none;
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 0.25rem 0.5rem;
    cursor: pointer;
    color: var(--text-dim);
    font-size: 0.85rem;
    line-height: 1;
    transition: border-color 0.15s, color 0.15s;
  }

  .theme-toggle:hover {
    border-color: var(--brand);
    color: var(--text);
  }
"""

# Light theme CSS variables (added as @media + [data-theme] rules)
LIGHT_DARK_CSS = """\

  /* ── Light theme ─────────────────────────────────────────── */
  :root[data-theme="light"] {
    --bg: #ffffff;
    --surface: #f8fafc;
    --surface-2: #f1f5f9;
    --border: #e2e8f0;
    --text: #334155;
    --text-dim: #64748b;
    --text-bright: #0f172a;
    --brand: #4f46e5;
    --nav-bg: rgba(255, 255, 255, 0.85);
    --code-bg: #f8fafc;
    --shadow-hover: rgba(0, 0, 0, 0.08);
  }

  :root[data-theme="dark"], :root:not([data-theme]) {
    --brand: #818cf8;
    --nav-bg: rgba(10, 10, 15, 0.85);
    --code-bg: #12121a;
    --shadow-hover: rgba(0, 0, 0, 0.4);
  }

  @media (prefers-color-scheme: light) {
    :root:not([data-theme]) {
      --bg: #ffffff;
      --surface: #f8fafc;
      --surface-2: #f1f5f9;
      --border: #e2e8f0;
      --text: #334155;
      --text-dim: #64748b;
      --text-bright: #0f172a;
      --brand: #4f46e5;
      --nav-bg: rgba(255, 255, 255, 0.85);
      --code-bg: #f8fafc;
      --shadow-hover: rgba(0, 0, 0, 0.08);
    }
  }

  /* ── Light-mode SVG overrides ───────────────────────────── */
  :root[data-theme="light"] svg text[fill="#e0e0e8"],
  :root[data-theme="light"] svg text[fill="#ffffff"] {
    fill: #0f172a;
  }

  :root[data-theme="light"] svg text[fill="#8888a0"] {
    fill: #64748b;
  }

  :root[data-theme="light"] svg rect[fill="#12121a"],
  :root[data-theme="light"] svg rect[fill="#1a1a28"] {
    fill: #f1f5f9;
  }

  :root[data-theme="light"] svg rect[stroke="#2a2a3a"],
  :root[data-theme="light"] svg rect[stroke="#3a3a5a"] {
    stroke: #e2e8f0;
  }

  :root[data-theme="light"] svg line[stroke="#2a2a3a"] {
    stroke: #e2e8f0;
  }

  @media (prefers-color-scheme: light) {
    :root:not([data-theme]) svg text[fill="#e0e0e8"],
    :root:not([data-theme]) svg text[fill="#ffffff"] {
      fill: #0f172a;
    }
    :root:not([data-theme]) svg text[fill="#8888a0"] {
      fill: #64748b;
    }
    :root:not([data-theme]) svg rect[fill="#12121a"],
    :root:not([data-theme]) svg rect[fill="#1a1a28"] {
      fill: #f1f5f9;
    }
    :root:not([data-theme]) svg rect[stroke="#2a2a3a"],
    :root:not([data-theme]) svg rect[stroke="#3a3a5a"] {
      stroke: #e2e8f0;
    }
    :root:not([data-theme]) svg line[stroke="#2a2a3a"] {
      stroke: #e2e8f0;
    }
  }

  .card:hover {
    box-shadow: 0 8px 32px var(--shadow-hover);
  }
"""

# Footer CSS
FOOTER_CSS = """\

  /* ── Unified footer ──────────────────────────────────────── */
  .ref-footer {
    text-align: center;
    padding: 2rem 0 1.5rem;
    border-top: 1px solid var(--border);
    margin-top: 3rem;
  }

  .ref-footer-nav {
    display: flex;
    justify-content: center;
    flex-wrap: wrap;
    gap: 1.5rem;
    margin-bottom: 1rem;
  }

  .ref-footer-nav a {
    color: var(--text-dim);
    text-decoration: none;
    font-size: 0.8rem;
    transition: color 0.15s;
  }

  .ref-footer-nav a:hover { color: var(--brand); }

  .ref-footer-copy {
    font-size: 0.75rem;
    color: var(--text-dim);
  }

  .ref-footer-copy a {
    color: var(--brand);
    text-decoration: none;
  }

  .ref-footer-copy a:hover { text-decoration: underline; }
"""

# Theme toggle JS
THEME_JS = """\
<script>
(function() {
  var root = document.documentElement;
  var btn = document.getElementById('theme-toggle');
  var stored = localStorage.getItem('adk-fluent-theme');

  function applyTheme(theme) {
    root.setAttribute('data-theme', theme);
    btn.textContent = theme === 'dark' ? '\\u2600' : '\\u263E';
    btn.setAttribute('aria-label', theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme');
    localStorage.setItem('adk-fluent-theme', theme);
  }

  function getSystemTheme() {
    return window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark';
  }

  if (stored) {
    applyTheme(stored);
  } else {
    applyTheme(getSystemTheme());
  }

  btn.addEventListener('click', function() {
    var current = root.getAttribute('data-theme') || getSystemTheme();
    applyTheme(current === 'dark' ? 'light' : 'dark');
  });

  window.matchMedia('(prefers-color-scheme: light)').addEventListener('change', function(e) {
    if (!localStorage.getItem('adk-fluent-theme')) {
      applyTheme(e.matches ? 'light' : 'dark');
    }
  });
})();
</script>
"""


def make_nav_html(back_text: str, back_href: str) -> str:
    """Generate the navigation bar HTML."""
    # The HTML files are served from the root of the build output (via html_extra_path),
    # so relative links go directly to user-guide/xxx.html
    return f"""\
<nav class="ref-nav" role="navigation" aria-label="Reference navigation">
  <div class="ref-nav-left">
    <a class="ref-nav-logo" href="index.html">adk-fluent</a>
    <span class="ref-nav-sep">/</span>
    <a class="ref-nav-back" href="{back_href}">&larr; {back_text}</a>
  </div>
  <div class="ref-nav-right">
    <a class="ref-nav-link" href="user-guide/index.html">User Guide</a>
    <a class="ref-nav-link" href="generated/api/index.html">API</a>
    <a class="ref-nav-link" href="https://github.com/vamsiramakrishnan/adk-fluent" target="_blank" rel="noopener">GitHub</a>
    <button class="theme-toggle" id="theme-toggle" aria-label="Toggle theme">&#x263E;</button>
  </div>
</nav>
"""


def make_footer_html(title: str, related_page: str, related_text: str) -> str:
    """Generate the unified footer HTML."""
    return f"""\
<div class="ref-footer">
  <div class="ref-footer-nav">
    <a href="{related_page}">&larr; Back to {related_text}</a>
    <a href="user-guide/index.html">User Guide</a>
    <a href="index.html">Home</a>
    <a href="generated/api/index.html">API Reference</a>
    <a href="https://pypi.org/project/adk-fluent/" target="_blank" rel="noopener">PyPI</a>
    <a href="https://github.com/vamsiramakrishnan/adk-fluent" target="_blank" rel="noopener">GitHub</a>
  </div>
  <div class="ref-footer-copy">
    {title} &mdash; <a href="index.html">adk-fluent</a> documentation
  </div>
</div>
"""


def transform_file(filepath: Path) -> None:
    """Transform a single HTML reference file."""
    name = filepath.name
    meta = FILE_META.get(name)
    if not meta:
        print(f"  SKIP {name} (no metadata)")
        return

    back_text, back_href, related_page = meta
    content = filepath.read_text()
    original = content

    # 1. Inject --brand and --nav-bg into existing :root if missing
    if "--brand:" not in content:
        # Add brand/nav-bg to the existing dark :root block
        content = content.replace(
            "--mono:",
            "--brand: #818cf8;\n    --nav-bg: rgba(10, 10, 15, 0.85);\n    --code-bg: #12121a;\n    --shadow-hover: rgba(0, 0, 0, 0.4);\n\n    --mono:",
        )

    # 2. Inject light/dark theme CSS before the closing </style>
    if 'data-theme="light"' not in content:
        content = content.replace("</style>", LIGHT_DARK_CSS + NAV_CSS + FOOTER_CSS + "</style>")

    # 3. Inject nav bar after <body> (or after <body>\n)
    if '<nav class="ref-nav"' not in content:
        nav_html = make_nav_html(back_text, back_href)
        content = content.replace("<body>\n", "<body>\n" + nav_html + "\n", 1)
        if '<nav class="ref-nav"' not in content:
            # Fallback: <body> without trailing newline
            content = content.replace("<body>", "<body>\n" + nav_html + "\n", 1)

    # 4. Replace existing footer or add one before </body>
    if 'class="ref-footer"' not in content:
        title_match = re.search(r"<title>([^<]+)</title>", content)
        title = title_match.group(1) if title_match else "Reference"
        footer_html = make_footer_html(title, related_page, back_text)

        # Try to replace existing footer patterns (in body HTML only)
        footer_patterns = [
            # Pattern: <footer>...</footer>
            r"<footer>.*?</footer>",
            # Pattern: <div class="footer">...(single line)...</div>
            r'(?<=\n)  <!-- Footer -->\n  <div class="footer">[^<]*</div>',
            # Pattern: inline footer div with style
            r'<div style="text-align:center;[^"]*padding[^"]*">.*?</div>',
        ]

        replaced = False
        for pattern in footer_patterns:
            if re.search(pattern, content, re.DOTALL):
                content = re.sub(pattern, footer_html, content, count=1, flags=re.DOTALL)
                replaced = True
                break

        if not replaced:
            # Insert before </body>
            content = content.replace(
                "\n</body>",
                "\n" + footer_html + "\n</body>",
            )

    # 5. Inject theme toggle JS before </body>
    if "theme-toggle" in content and "applyTheme" not in content:
        content = content.replace("</body>", THEME_JS + "\n</body>")

    if content != original:
        filepath.write_text(content)
        print(f"  UPDATED {name}")
    else:
        print(f"  NO CHANGE {name}")


def main():
    print("Updating HTML reference pages...")
    for html_file in sorted(DOCS_DIR.glob("*-reference.html")):
        transform_file(html_file)
    print("Done.")


if __name__ == "__main__":
    main()
