"""Sphinx configuration for adk-fluent documentation."""

import datetime
import warnings

# sphinx-hoverxref 1.4.x uses deprecated Sphinx _Opt tuple interface;
# suppress until upstream ships a fix.
warnings.filterwarnings("ignore", message=".*_Opt.*tuple interface.*deprecated", category=DeprecationWarning)
warnings.filterwarnings("ignore", message=".*_Opt.*tuple interface.*deprecated", category=PendingDeprecationWarning)

project = "adk-fluent"
version = "0.13.2"
release = "0.13.2"
copyright = "2025, adk-fluent contributors"
author = "adk-fluent contributors"

# Current year for display purposes
_year = datetime.datetime.now().year
if _year > 2025:
    copyright = f"2025–{_year}, adk-fluent contributors"

extensions = [
    "myst_parser",
    "sphinx_design",
    "sphinx_copybutton",
    "sphinx.ext.intersphinx",
    "sphinxcontrib.mermaid",
    "hoverxref.extension",
    "sphinxext.opengraph",
]

# Hoverxref settings — tooltips for cross-references
hoverxref_auto_ref = True
hoverxref_domains = ["py"]
hoverxref_role_types = {
    "hoverxref": "tooltip",
    "ref": "modal",
    "class": "tooltip",
    "meth": "tooltip",
    "func": "tooltip",
}
hoverxref_intersphinx = [
    "python",
]

# OpenGraph settings — social sharing previews
ogp_site_url = "https://vamsiramakrishnan.github.io/adk-fluent/"
ogp_image = "https://vamsiramakrishnan.github.io/adk-fluent/_static/og-card.svg"
ogp_description_length = 200
ogp_type = "website"
ogp_custom_meta_tags = [
    '<meta name="twitter:card" content="summary_large_image">',
]

# Mermaid settings — CDN for GitHub Pages, theme-aware dark mode
mermaid_version = "11"
mermaid_init_config = {
    "startOnLoad": False,
    "theme": "base",
    "themeVariables": {
        "primaryColor": "#FFF3E0",
        "primaryTextColor": "#1A1A1A",
        "primaryBorderColor": "#E65100",
        "lineColor": "#757575",
        "secondaryColor": "#FFF8E1",
        "tertiaryColor": "#ecfdf5",
        "fontFamily": "'IBM Plex Sans', -apple-system, BlinkMacSystemFont, sans-serif",
        "fontSize": "14px",
    },
}

# MyST settings — full Markdown feature set
myst_enable_extensions = [
    "colon_fence",
    "fieldlist",
    "deflist",
    "attrs_block",
    "substitution",
    "tasklist",
]
myst_heading_anchors = 4
myst_fence_as_directive = ["mermaid"]

# Intersphinx — cross-reference to Python stdlib docs
intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
}

# Theme — Furo with custom brand colors and typography
html_theme = "furo"
html_title = "adk-fluent"
html_theme_options = {
    "source_repository": "https://github.com/vamsiramakrishnan/adk-fluent",
    "source_branch": "master",
    "source_directory": "docs/",
    "announcement": (
        "adk-fluent v0.13.2 is out &mdash; "
        '<a href="https://pypi.org/project/adk-fluent/">Install from PyPI</a> '
        'or <a href="https://github.com/vamsiramakrishnan/adk-fluent">star on GitHub</a>'
    ),
    "sidebar_hide_name": False,
    "navigation_with_keys": True,
    "footer_icons": [
        {
            "name": "GitHub",
            "url": "https://github.com/vamsiramakrishnan/adk-fluent",
            "html": '<svg stroke="currentColor" fill="currentColor" stroke-width="0" viewBox="0 0 16 16"><path fill-rule="evenodd" d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"></path></svg>',
            "class": "",
        },
        {
            "name": "PyPI",
            "url": "https://pypi.org/project/adk-fluent/",
            "html": '<svg stroke="currentColor" fill="currentColor" stroke-width="0" viewBox="0 0 24 24"><path d="M12 0L1.5 6v12L12 24l10.5-6V6L12 0zm0 2.18l8.25 4.73v9.18L12 20.82l-8.25-4.73V6.91L12 2.18z"/></svg>',
            "class": "",
        },
    ],
    "light_css_variables": {
        "color-brand-primary": "#E65100",
        "color-brand-content": "#D84315",
        "color-admonition-background": "#FFF3E0",
        "font-stack": "'IBM Plex Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif",
        "font-stack--monospace": "'IBM Plex Mono', 'SFMono-Regular', Consolas, ui-monospace, monospace",
        "font-stack--headings": "'IBM Plex Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif",
        "font-size--normal": "15px",
        "font-size--small": "13px",
        "font-size--small--2": "12px",
        "content-padding": "3.5em",
        "sidebar-width": "17rem",
        "sidebar-width--mobile": "80vw",
        "color-background-primary": "#FFFFFF",
        "color-background-secondary": "#FAFAFA",
        "color-background-border": "#E0E0E0",
        "color-foreground-primary": "#1A1A1A",
        "color-foreground-secondary": "#424242",
        "color-sidebar-background": "#FAFAFA",
        "color-sidebar-link-text--top-level": "#1A1A1A",
        "color-highlighted-background": "#FFF8E1",
        "color-code-background": "#F5F5F5",
    },
    "dark_css_variables": {
        "color-brand-primary": "#FFB74D",
        "color-brand-content": "#FFCC80",
        "color-admonition-background": "#2E2E2E",
        "color-background-primary": "#171717",
        "color-background-secondary": "#1E1E1E",
        "color-background-border": "#333333",
        "color-foreground-primary": "#E0E0E0",
        "color-foreground-secondary": "#BDBDBD",
        "color-foreground-muted": "#9E9E9E",
        "color-sidebar-background": "#1A1A1A",
        "color-highlighted-background": "#2E2200",
        "color-code-background": "#1E1E1E",
    },
    "top_of_page_buttons": ["view", "edit"],
}

html_favicon = "_static/favicon.svg"
html_logo = "_static/logo.svg"
html_baseurl = "https://vamsiramakrishnan.github.io/adk-fluent/"

pygments_style = "friendly"
pygments_dark_style = "monokai"

copybutton_prompt_text = r">>> |\.\.\. |\$ |In \[\d+\]: | {2,5}\.\.\.: | {5,8}: "
copybutton_prompt_is_regexp = True

html_static_path = ["_static"]
html_css_files = [
    # Load IBM Plex Sans and IBM Plex Mono from Google Fonts CDN
    (
        "https://fonts.googleapis.com/css2?"
        "family=IBM+Plex+Sans:wght@400;500;600;700"
        "&family=IBM+Plex+Mono:wght@400;500;600"
        "&display=swap"
    ),
    "custom.css",
]
html_js_files = ["custom.js"]

# Source settings
source_suffix = {
    ".md": "markdown",
    ".rst": "restructuredtext",
}
exclude_patterns = [
    "_build",
    "plans",
    "other_specs",
    "architecture",
    "generated/cookbook/conftest.md",
    "cookbook/COOKBOOK_MASTER_PLAN.md",
]

# Copy standalone HTML references and llms.txt into the build output as-is
html_extra_path = [
    "user-guide/pcs-visual-reference.html",
    "user-guide/operator-algebra-reference.html",
    "user-guide/module-lifecycle-reference.html",
    "user-guide/data-flow-reference.html",
    "user-guide/delegation-reference.html",
    "user-guide/execution-modes-reference.html",
    "user-guide/a2a-topology-reference.html",
    "llms.txt",
]

# Suppress warnings for auto-generated cross-references and duplicate targets
# - myst.header: heading level warnings in generated docs
# - myst.xref_missing: cross-references to builder anchors not in seed (optional ADK extensions)
# - docutils: duplicate target names from case variants (MCPTool vs McpTool)
# - hoverxref.ref_node_not_found: hoverxref warnings on auto-generated stubs that might be missing references
suppress_warnings = ["myst.header", "myst.xref_missing", "docutils", "hoverxref.ref_node_not_found"]
