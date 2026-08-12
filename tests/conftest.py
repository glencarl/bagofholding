"""Shared fixtures for the bagofholding test suite."""

import importlib.util
import json
import sys
import threading
from http.server import HTTPServer
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SERVICE_DIR = REPO_ROOT / "service"
CMDLINE_DIR = REPO_ROOT / "cmdline"


def _load_module(name, path):
    """Import a standalone script (not part of a package) by file path."""
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def service_module(tmp_path, monkeypatch):
    """Import service/server.py with DATA_FILE redirected to a scratch file.

    Re-imports fresh each test so no state (or monkeypatching) leaks between
    tests, and so the real service/inventory_data.json is never touched.
    """
    module = _load_module("service_server", SERVICE_DIR / "server.py")
    monkeypatch.setattr(module, "DATA_FILE", str(tmp_path / "inventory_data.json"))
    yield module
    del sys.modules["service_server"]


@pytest.fixture
def inventory_module(tmp_path, monkeypatch):
    """Import cmdline/inventory.py with DATA_FILE redirected to a scratch file.

    Re-imports fresh each test so no state leaks between tests, and so the
    real cmdline/inventory_data.json is never touched.
    """
    module = _load_module("cmdline_inventory", CMDLINE_DIR / "inventory.py")
    monkeypatch.setattr(module, "DATA_FILE", str(tmp_path / "inventory_data.json"))
    yield module
    del sys.modules["cmdline_inventory"]


@pytest.fixture
def live_server(service_module, monkeypatch):
    """Run the inventory HTTP service on an ephemeral port for the test.

    Static-file requests are served relative to the process's working
    directory (that's how SimpleHTTPRequestHandler works), so this also
    chdirs into service/ for the lifetime of the fixture.
    """
    monkeypatch.chdir(SERVICE_DIR)
    httpd = HTTPServer(("127.0.0.1", 0), service_module.InventoryHTTPRequestHandler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{httpd.server_port}"
    finally:
        httpd.shutdown()
        thread.join(timeout=5)
        httpd.server_close()


@pytest.fixture
def sample_inventory():
    return {
        "beamlight": {
            "name": "beamlight",
            "quantity": 4,
            "unit": "boxes",
            "category": "support",
            "location": "truck",
            "low_stock_threshold": 1,
            "last_updated": "2026-08-11T02:45:41",
        }
    }


@pytest.fixture
def data_file_with(tmp_path):
    """Write arbitrary content to the path a test's DATA_FILE points at.

    Works with either `service_module` or `inventory_module` — both expose a
    `DATA_FILE` attribute.
    """

    def _write(module, content):
        path = Path(module.DATA_FILE)
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, str):
            path.write_text(content, encoding="utf-8")
        else:
            path.write_text(json.dumps(content), encoding="utf-8")
        return path

    return _write
