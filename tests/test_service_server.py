"""Basic tests for service/server.py, the inventory HTTP API + static server."""

import json
import urllib.error
import urllib.request

import pytest


def _get(base_url, path):
    with urllib.request.urlopen(f"{base_url}{path}") as resp:
        return resp.status, json.loads(resp.read())


def _put(base_url, path, payload, method="PUT"):
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(f"{base_url}{path}", data=body, method=method)
    return urllib.request.urlopen(req)


class TestApiInventory:
    def test_get_returns_empty_dict_when_no_data_file_exists(self, live_server):
        status, data = _get(live_server, "/api/inventory")
        assert status == 200
        assert data == {}

    def test_get_returns_json_content_type(self, live_server):
        with urllib.request.urlopen(f"{live_server}/api/inventory") as resp:
            assert resp.headers["Content-Type"] == "application/json; charset=utf-8"

    def test_put_then_get_round_trips_data(self, live_server, sample_inventory):
        resp = _put(live_server, "/api/inventory", sample_inventory)
        assert resp.status == 204

        status, data = _get(live_server, "/api/inventory")
        assert status == 200
        assert data == sample_inventory

    def test_put_persists_to_disk(self, live_server, service_module, sample_inventory):
        _put(live_server, "/api/inventory", sample_inventory)
        with open(service_module.DATA_FILE, "r", encoding="utf-8") as f:
            assert json.load(f) == sample_inventory

    def test_put_invalid_json_returns_400(self, live_server):
        req = urllib.request.Request(
            f"{live_server}/api/inventory",
            data=b"not valid json",
            method="PUT",
        )
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            urllib.request.urlopen(req)
        assert exc_info.value.code == 400

    def test_post_is_accepted_as_alias_for_put(self, live_server, sample_inventory):
        resp = _put(live_server, "/api/inventory", sample_inventory, method="POST")
        assert resp.status == 204

        status, data = _get(live_server, "/api/inventory")
        assert data == sample_inventory

    def test_trailing_slash_is_treated_as_same_endpoint(self, live_server, sample_inventory):
        resp = _put(live_server, "/api/inventory/", sample_inventory)
        assert resp.status == 204

    def test_corrupt_data_file_is_treated_as_empty_inventory(
        self, live_server, service_module, data_file_with
    ):
        data_file_with(service_module, "{not valid json")
        status, data = _get(live_server, "/api/inventory")
        assert status == 200
        assert data == {}


class TestStaticFileFallback:
    def test_non_api_get_serves_static_file(self, live_server):
        with urllib.request.urlopen(f"{live_server}/inventory.html") as resp:
            assert resp.status == 200
            assert b"<html" in resp.read().lower()

    def test_missing_static_file_returns_404(self, live_server):
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            urllib.request.urlopen(f"{live_server}/does-not-exist.html")
        assert exc_info.value.code == 404
