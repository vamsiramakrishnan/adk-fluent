"""Sphinx configuration for adk-fluent documentation."""

project = "adk-fluent"
copyright = "2025, adk-fluent contributors"
author = "adk-fluent contributors"

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
ogp_image = "https://vamsiramakrishnan.github.io/adk-fluent/_static/logo.png"
ogp_description_length = 200
ogp_type = "website"
ogp_custom_meta_tags = [
    '<meta name="twitter:card" content="summary_large_image">',
]

# Mermaid settings - use CDN for GitHub Pages (no server-side rendering needed)
mermaid_version = "11"

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
        "color-brand-primary": "#4f46e5",
        "color-brand-content": "#4338ca",
        "font-stack": "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
        "font-stack--monospace": "'JetBrains Mono', 'Fira Code', 'Cascadia Code', monospace",
        "content-padding": "3em",
    },
    "dark_css_variables": {
        "color-brand-primary": "#818cf8",
        "color-brand-content": "#6366f1",
    },
    "top_of_page_buttons": ["view", "edit"],
}

pygments_style = "github-light"
pygments_dark_style = "github-dark"

copybutton_prompt_text = r">>> |\.\.\. |\$ |In \[\d+\]: | {2,5}\.\.\.: | {5,8}: "
copybutton_prompt_is_regexp = True

html_static_path = ["_static"]
html_css_files = ["custom.css"]

# Source settings
source_suffix = {
    ".md": "markdown",
    ".rst": "restructuredtext",
}
exclude_patterns = [
    "_build",
    "plans",
    "other_specs",
    "generated/cookbook/conftest.md",
    "cookbook/COOKBOOK_MASTER_PLAN.md",
]

# Copy standalone HTML references and llms.txt into the build output as-is
html_extra_path = [
    "user-guide/pcs-visual-reference.html",
    "user-guide/operator-algebra-reference.html",
    "llms.txt",
]

# Suppress warnings for auto-generated cross-references and duplicate targets
# - myst.header: heading level warnings in generated docs
# - myst.xref_missing: cross-references to builder anchors not in seed (optional ADK extensions)
# - docutils: duplicate target names from case variants (MCPTool vs McpTool)
# - hoverxref.ref_node_not_found: hoverxref warnings on auto-generated stubs that might be missing references
suppress_warnings = ["myst.header", "myst.xref_missing", "docutils", "hoverxref.ref_node_not_found"]
