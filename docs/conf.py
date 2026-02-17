"""Sphinx configuration for adk-fluent documentation."""

project = "adk-fluent"
copyright = "2025, adk-fluent contributors"
author = "adk-fluent contributors"

extensions = [
    "myst_parser",
    "sphinx_design",
    "sphinx_copybutton",
    "sphinx.ext.intersphinx",
]

# MyST settings
myst_enable_extensions = [
    "colon_fence",
    "fieldlist",
    "deflist",
    "attrs_block",
]
myst_heading_anchors = 3

# Intersphinx
intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
}

# Theme
html_theme = "furo"
html_title = "adk-fluent"
html_theme_options = {
    "source_repository": "https://gitlab.com/google-cloud-ce/googlers/vamramak/adk-fluent",
    "source_branch": "master",
    "source_directory": "docs/",
}

# Source settings
source_suffix = {
    ".md": "markdown",
    ".rst": "restructuredtext",
}
exclude_patterns = ["_build", "plans", "generated/cookbook/conftest.md"]

# Suppress warnings for missing toctree references in auto-generated files
suppress_warnings = ["myst.header"]
