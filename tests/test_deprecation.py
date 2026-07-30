"""GEN-4785: the final PyPI release must be loudly deprecated at every entry
point that represents the DOWNLOADED package — and quiet on the official paths
(hosted --http mode, git/editable installs).

These tests fail on a tree without the deprecation code:
- no DEPRECATION_NOTICE export
- no import-time DeprecationWarning for index installs
- no stderr banner on the stdio CLI path
"""
from __future__ import annotations

import importlib
import sys
import warnings

import pytest


def _reload_package(monkeypatch, direct_url_text):
    """Reload gen_mcp_server with distribution provenance forced.

    direct_url_text=None simulates a PyPI (index) install; a JSON string
    simulates a git/editable install (PEP 610 direct_url.json present).
    """
    import importlib.metadata as md

    class _FakeDist:
        def read_text(self, name):
            assert name == "direct_url.json"
            return direct_url_text

    real_distribution = md.distribution

    def fake_distribution(name):
        # Only fake our own distribution — other packages (fastmcp etc.) do
        # real metadata lookups during import.
        if name == "gen-mcp-server":
            return _FakeDist()
        return real_distribution(name)

    monkeypatch.setattr(md, "distribution", fake_distribution)
    for mod in [m for m in list(sys.modules) if m.startswith("gen_mcp_server")]:
        del sys.modules[mod]
    return importlib.import_module("gen_mcp_server")


def test_index_install_warns_on_import(monkeypatch):
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        pkg = _reload_package(monkeypatch, direct_url_text=None)
    dep = [w for w in caught if issubclass(w.category, DeprecationWarning)]
    assert dep, "PyPI install must emit DeprecationWarning on import"
    assert "mcp.gen.pro" in str(dep[0].message)
    assert "mcp.gen.pro" in pkg.DEPRECATION_NOTICE


def test_git_install_is_quiet_on_import(monkeypatch):
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        _reload_package(monkeypatch, direct_url_text='{"url": "https://github.com/poweredbyGEN/gen-mcp-server"}')
    dep = [w for w in caught if issubclass(w.category, DeprecationWarning)]
    assert not dep, "git/editable installs (hosted server, dev) must NOT warn"


def test_stdio_cli_prints_banner_to_stderr(monkeypatch, capsys):
    import gen_mcp_server.__main__ as entry

    monkeypatch.setattr(sys, "argv", ["gen-mcp-server"])  # stdio mode
    monkeypatch.delenv("GEN_API_KEY", raising=False)      # fail fast after banner
    with pytest.raises(SystemExit):
        entry.main()
    err = capsys.readouterr().err
    assert "DEPRECATED" in err and "mcp.gen.pro" in err


def test_http_mode_has_no_banner(monkeypatch, capsys):
    import types

    import gen_mcp_server.__main__ as entry

    ran = {}
    fake_uvicorn = types.SimpleNamespace(run=lambda app, **kw: ran.update(app=app, **kw))
    monkeypatch.setitem(sys.modules, "uvicorn", fake_uvicorn)
    monkeypatch.setattr(sys, "argv", ["gen-mcp-server", "--http", "--port", "8091"])
    entry.main()
    err = capsys.readouterr().err
    assert "DEPRECATED" not in err, "hosted --http mode is the official surface — no banner"
    assert ran.get("port") == 8091 and ran.get("app") is not None
