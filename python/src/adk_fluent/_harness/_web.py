"""Web tools — fetch URLs and search the web.

Harnesses like Claude Code and Gemini CLI can fetch web pages and
search the internet. This module provides two approaches:

1. **ADK-native tools** (preferred): Wraps existing ``UrlContextTool``
   and ``GoogleSearchTool`` builders from adk-fluent's tool module.
2. **Standalone closures** (fallback): Simple ``urllib``-based fetch
   that works without ADK search extras installed.

Usage::

    tools = H.web()                     # [web_fetch] + GoogleSearchTool
    tools = H.web(search=False)         # [web_fetch] only
    tools = H.web(search_provider=fn)   # custom search tool

Reuses: ``adk_fluent.tool.UrlContextTool``, ``adk_fluent.tool.GoogleSearchTool``,
and ``T.google_search()`` factory.
"""

from __future__ import annotations

import urllib.error
import urllib.request
from collections.abc import Callable
from html.parser import HTMLParser

from adk_fluent._harness._sandbox import SandboxPolicy

__all__ = ["make_web_fetch", "web_tools"]


class _TextExtractor(HTMLParser):
    """Minimal HTML-to-text extractor."""

    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []
        self._skip = False

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag in ("script", "style", "noscript"):
            self._skip = True

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style", "noscript"):
            self._skip = False

    def handle_data(self, data: str) -> None:
        if not self._skip:
            stripped = data.strip()
            if stripped:
                self._parts.append(stripped)

    def get_text(self) -> str:
        return "\n".join(self._parts)


def _extract_text(html: str) -> str:
    """Extract readable text from HTML."""
    parser = _TextExtractor()
    parser.feed(html)
    return parser.get_text()


def make_web_fetch(
    sandbox: SandboxPolicy,
    *,
    max_bytes: int = 100_000,
    timeout: int = 30,
) -> Callable:
    """Create a sandboxed web fetch tool.

    Respects ``sandbox.allow_network``. Returns extracted text from HTML
    or raw text for other content types. This is the standalone fallback;
    when ADK's ``UrlContextTool`` is available, prefer using it via
    ``web_tools()``.

    Args:
        sandbox: Sandbox policy (checks allow_network).
        max_bytes: Maximum response size in bytes.
        timeout: Request timeout in seconds.
    """

    def web_fetch(url: str) -> str:
        """Fetch a URL and return its text content.

        Extracts readable text from HTML pages. Returns raw text for
        non-HTML responses. Respects sandbox network policy.

        Args:
            url: The URL to fetch (must be http:// or https://).
        """
        if not sandbox.allow_network:
            return "Error: network access is disabled by sandbox policy."

        if not url.startswith(("http://", "https://")):
            return "Error: URL must start with http:// or https://"

        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "adk-fluent-harness/1.0"},
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                content_type = resp.headers.get("Content-Type", "")
                data = resp.read(max_bytes)
                text = data.decode("utf-8", errors="replace")

                if "html" in content_type.lower():
                    text = _extract_text(text)

                if len(data) >= max_bytes:
                    text += f"\n... (truncated to {max_bytes} bytes)"
                return text
        except urllib.error.HTTPError as e:
            return f"Error: HTTP {e.code} — {e.reason}"
        except urllib.error.URLError as e:
            return f"Error: {e.reason}"
        except TimeoutError:
            return f"Error: request timed out after {timeout}s"
        except Exception as e:
            return f"Error fetching URL: {e}"

    return web_fetch


def _try_adk_url_context_tool() -> object | None:
    """Try to get ADK's UrlContextTool."""
    try:
        from adk_fluent.tool import UrlContextTool

        return UrlContextTool().build()
    except Exception:
        return None


def _try_adk_google_search_tool() -> object | None:
    """Try to get ADK's GoogleSearchTool."""
    try:
        from adk_fluent.tool import GoogleSearchTool

        return GoogleSearchTool().build()
    except Exception:
        return None


def web_tools(
    sandbox: SandboxPolicy,
    *,
    search: bool = True,
    search_provider: Callable | None = None,
    max_bytes: int = 100_000,
    timeout: int = 30,
    prefer_adk_native: bool = True,
) -> list:
    """Create the web tool set.

    When ``prefer_adk_native`` is True (default), attempts to use ADK's
    built-in ``UrlContextTool`` and ``GoogleSearchTool``. Falls back to
    the standalone ``web_fetch`` closure if ADK tools aren't available.

    Args:
        sandbox: Sandbox policy.
        search: Include web search tool.
        search_provider: Custom search tool (replaces default).
        max_bytes: Max response size for standalone web_fetch.
        timeout: Request timeout for standalone web_fetch.
        prefer_adk_native: Try ADK built-in tools first.

    Returns:
        List of tool functions / ADK tool objects.
    """
    if not sandbox.allow_network:
        # Return a single stub that explains network is disabled
        def web_unavailable() -> str:
            """Web tools are unavailable — network access is disabled by sandbox policy."""
            return "Error: network access is disabled by sandbox policy."

        return [web_unavailable]

    tools: list = []

    # URL fetching
    if prefer_adk_native:
        adk_url_tool = _try_adk_url_context_tool()
        if adk_url_tool is not None:
            tools.append(adk_url_tool)
        else:
            tools.append(make_web_fetch(sandbox, max_bytes=max_bytes, timeout=timeout))
    else:
        tools.append(make_web_fetch(sandbox, max_bytes=max_bytes, timeout=timeout))

    # Search
    if search:
        if search_provider is not None:
            tools.append(search_provider)
        elif prefer_adk_native:
            adk_search = _try_adk_google_search_tool()
            if adk_search is not None:
                tools.append(adk_search)
            # No fallback for search — it requires an API key
        else:
            pass  # No standalone search available

    return tools
