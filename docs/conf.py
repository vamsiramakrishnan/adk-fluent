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

# Hoverxref settings
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

# OpenGraph settings
ogp_site_url = "https://vamsiramakrishnan.github.io/adk-fluent/"
ogp_image = "https://vamsiramakrishnan.github.io/adk-fluent/_static/logo.png"
ogp_description_length = 200
ogp_type = "website"
ogp_custom_meta_tags = [
    '<meta name="twitter:card" content="summary_large_image">',
]

# Mermaid settings - use CDN for GitHub Pages (no server-side rendering needed)
mermaid_version = "11"

# MyST settings
myst_enable_extensions = [
    "colon_fence",
    "fieldlist",
    "deflist",
    "attrs_block",
]
myst_heading_anchors = 3
myst_fence_as_directive = ["mermaid"]

# Intersphinx
intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
}

# Theme
html_theme = "furo"
html_title = "adk-fluent"
html_theme_options = {
    "source_repository": "https://github.com/vamsiramakrishnan/adk-fluent",
    "source_branch": "master",
    "source_directory": "docs/",
    "light_css_variables": {
        "color-brand-primary": "#4f46e5",
        "color-brand-content": "#4338ca",
        "font-stack": "Inter, sans-serif",
        "font-stack--monospace": "'JetBrains Mono', 'Fira Code', monospace",
    },
    "dark_css_variables": {
        "color-brand-primary": "#818cf8",
        "color-brand-content": "#6366f1",
    },
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
