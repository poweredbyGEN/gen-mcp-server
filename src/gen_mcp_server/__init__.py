"""GEN MCP server package.

The downloadable PyPI package is DEPRECATED (final release — GEN-4785): the
official GEN MCP is the hosted server at https://mcp.gen.pro. The code stays
fully functional so existing integrations keep working through their migration
window, but installing from PyPI warns on import and on CLI start.
"""
import warnings

DEPRECATION_NOTICE = (
    "The downloadable gen-mcp-server package is deprecated and this is its FINAL "
    "release. The official GEN MCP is the hosted server: configure your MCP client "
    "with url=https://mcp.gen.pro and header `Authorization: Bearer <gen_PAT>`. "
    "See https://mcp.gen.pro or https://api.gen.pro for setup."
)


def _installed_from_package_index() -> bool:
    """True only when this distribution came from a package index (PyPI).

    PEP 610: installs from git/URL/local-path (including `pip install -e .` and
    the hosted mcp.gen.pro deployment, which installs from the repo) carry a
    `direct_url.json`; index installs do not. That makes the warning target
    exactly the artifact being deprecated — the PyPI download — while the
    hosted server and dev checkouts stay quiet.
    """
    try:
        from importlib.metadata import distribution

        return distribution("gen-mcp-server").read_text("direct_url.json") is None
    except Exception:
        # Can't determine provenance (e.g. running from a plain source tree
        # that was never installed) — don't warn the official/dev paths.
        return False


if _installed_from_package_index():
    warnings.warn(DEPRECATION_NOTICE, DeprecationWarning, stacklevel=2)

from .server import mcp  # noqa: E402  (deprecation check must run first)

__all__ = ["mcp", "DEPRECATION_NOTICE"]
