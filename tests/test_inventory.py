"""Basic tests for cmdline/inventory.py, the interactive CLI's data layer."""

import json
import os


# ---------------------------------------------------------------------------
# load_inventory / save_inventory
# ---------------------------------------------------------------------------

class TestLoadInventory:
    def test_returns_empty_dict_when_no_data_file_exists(self, inventory_module):
        assert inventory_module.load_inventory() == {}

    def test_loads_existing_data(self, inventory_module, data_file_with, sample_inventory):
        data_file_with(inventory_module, sample_inventory)
        assert inventory_module.load_inventory() == sample_inventory

    def test_corrupt_json_returns_empty_dict(self, inventory_module, data_file_with, capsys):
        data_file_with(inventory_module, "{not valid json")
        result = inventory_module.load_inventory()
        assert result == {}
        assert "Warning" in capsys.readouterr().out

    def test_non_dict_json_returns_empty_dict(self, inventory_module, data_file_with):
        data_file_with(inventory_module, [1, 2, 3])
        assert inventory_module.load_inventory() == {}

    def test_backfills_missing_fields_on_legacy_records(self, inventory_module, data_file_with):
        # This is the shape that caused the original low-stock bug: an item
        # missing "low_stock_threshold" entirely.
        data_file_with(inventory_module, {"widget": {"name": "widget", "quantity": 3}})
        result = inventory_module.load_inventory()
        assert result["widget"]["low_stock_threshold"] == 0
        assert result["widget"]["category"] == "general"
        assert result["widget"]["location"] == ""


class TestSaveInventory:
    def test_writes_data_readable_back(self, inventory_module, sample_inventory):
        inventory_module.save_inventory(sample_inventory)
        with open(inventory_module.DATA_FILE) as f:
            assert json.load(f) == sample_inventory

    def test_no_leftover_temp_files(self, inventory_module, sample_inventory):
        inventory_module.save_inventory(sample_inventory)
        directory = os.path.dirname(inventory_module.DATA_FILE)
        stray = [f for f in os.listdir(directory) if f.startswith(".inventory_data-")]
        assert stray == []


# ---------------------------------------------------------------------------
# add_item / remove_item / update_item
# ---------------------------------------------------------------------------

class TestAddItem:
    def test_adds_new_item_with_defaults(self, inventory_module):
        inv = {}
        inventory_module.add_item(inv, "Widget", 5)
        assert inv["widget"]["name"] == "Widget"
        assert inv["widget"]["quantity"] == 5
        assert inv["widget"]["category"] == "general"

    def test_key_is_lowercased_and_stripped(self, inventory_module):
        inv = {}
        inventory_module.add_item(inv, "  Widget  ", 1)
        assert "widget" in inv
        assert inv["widget"]["name"] == "Widget"

    def test_adding_existing_item_increments_quantity(self, inventory_module):
        inv = {}
        inventory_module.add_item(inv, "Widget", 5)
        inventory_module.add_item(inv, "widget", 3)
        assert inv["widget"]["quantity"] == 8
        assert len(inv) == 1

    def test_persists_to_disk(self, inventory_module):
        inv = {}
        inventory_module.add_item(inv, "Widget", 5)
        assert inventory_module.load_inventory() == inv


class TestRemoveItem:
    def test_removes_item_entirely_when_no_quantity_given(self, inventory_module, sample_inventory):
        inv = dict(sample_inventory)
        inventory_module.remove_item(inv, "beamlight")
        assert "beamlight" not in inv

    def test_reduces_quantity_when_quantity_given(self, inventory_module, sample_inventory):
        inv = {k: dict(v) for k, v in sample_inventory.items()}
        inventory_module.remove_item(inv, "beamlight", 1)
        assert inv["beamlight"]["quantity"] == 3

    def test_removes_item_when_quantity_reaches_zero(self, inventory_module, sample_inventory):
        inv = {k: dict(v) for k, v in sample_inventory.items()}
        inventory_module.remove_item(inv, "beamlight", 4)
        assert "beamlight" not in inv

    def test_removes_item_when_quantity_goes_negative(self, inventory_module, sample_inventory):
        inv = {k: dict(v) for k, v in sample_inventory.items()}
        inventory_module.remove_item(inv, "beamlight", 999)
        assert "beamlight" not in inv

    def test_missing_item_does_not_raise_or_save(self, inventory_module, capsys):
        inv = {}
        inventory_module.remove_item(inv, "nonexistent")
        assert "not found" in capsys.readouterr().out
        assert not os.path.exists(inventory_module.DATA_FILE)


class TestUpdateItem:
    def test_updates_provided_fields(self, inventory_module, sample_inventory):
        inv = {k: dict(v) for k, v in sample_inventory.items()}
        inventory_module.update_item(inv, "beamlight", location="warehouse")
        assert inv["beamlight"]["location"] == "warehouse"

    def test_none_fields_are_left_unchanged(self, inventory_module, sample_inventory):
        inv = {k: dict(v) for k, v in sample_inventory.items()}
        inventory_module.update_item(inv, "beamlight", location=None, category=None)
        assert inv["beamlight"]["location"] == "truck"
        assert inv["beamlight"]["category"] == "support"

    def test_unknown_field_is_ignored(self, inventory_module, sample_inventory):
        inv = {k: dict(v) for k, v in sample_inventory.items()}
        inventory_module.update_item(inv, "beamlight", not_a_real_field="x")
        assert "not_a_real_field" not in inv["beamlight"]

    def test_missing_item_does_not_raise(self, inventory_module, capsys):
        inventory_module.update_item({}, "nonexistent", location="x")
        assert "not found" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# search_items / low_stock_items
# ---------------------------------------------------------------------------

class TestSearchItems:
    def test_matches_name_case_insensitively(self, inventory_module, sample_inventory):
        assert inventory_module.search_items(sample_inventory, "BEAM") == [
            sample_inventory["beamlight"]
        ]

    def test_matches_category(self, inventory_module, sample_inventory):
        assert inventory_module.search_items(sample_inventory, "support") == [
            sample_inventory["beamlight"]
        ]

    def test_matches_location(self, inventory_module, sample_inventory):
        assert inventory_module.search_items(sample_inventory, "truck") == [
            sample_inventory["beamlight"]
        ]

    def test_no_match_returns_empty_list(self, inventory_module, sample_inventory):
        assert inventory_module.search_items(sample_inventory, "nope") == []


class TestLowStockItems:
    def test_item_at_or_below_threshold_is_flagged(self, inventory_module):
        inv = {"a": {"name": "a", "quantity": 1, "low_stock_threshold": 1}}
        assert inventory_module.low_stock_items(inv) == [inv["a"]]

    def test_item_above_threshold_is_not_flagged(self, inventory_module):
        inv = {"a": {"name": "a", "quantity": 5, "low_stock_threshold": 1}}
        assert inventory_module.low_stock_items(inv) == []

    def test_threshold_of_zero_means_no_alert(self, inventory_module):
        inv = {"a": {"name": "a", "quantity": 0, "low_stock_threshold": 0}}
        assert inventory_module.low_stock_items(inv) == []

    def test_missing_threshold_key_does_not_raise(self, inventory_module):
        # Regression test for the original bug: a record saved under an old
        # schema (e.g. "threshold" instead of "low_stock_threshold").
        inv = {"a": {"name": "a", "quantity": 1}}
        assert inventory_module.low_stock_items(inv) == []


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------

class TestPrintTable:
    def test_empty_list_prints_placeholder(self, inventory_module, capsys):
        inventory_module.print_table([])
        assert "No items to display." in capsys.readouterr().out

    def test_prints_sorted_rows(self, inventory_module, capsys):
        items = [
            {"name": "Zed", "quantity": 1, "unit": "", "category": "c", "location": "", "last_updated": ""},
            {"name": "Alpha", "quantity": 2, "unit": "", "category": "c", "location": "", "last_updated": ""},
        ]
        inventory_module.print_table(items)
        out = capsys.readouterr().out
        assert out.index("Alpha") < out.index("Zed")


class TestPrintSummary:
    def test_reports_totals_and_categories(self, inventory_module, sample_inventory, capsys):
        inventory_module.print_summary(sample_inventory)
        out = capsys.readouterr().out
        assert "Total distinct items: 1" in out
        assert "Total quantity across all items: 4" in out
        assert "support" in out


# ---------------------------------------------------------------------------
# prompt_int
# ---------------------------------------------------------------------------

class TestPromptInt:
    def test_returns_parsed_int(self, inventory_module, monkeypatch):
        monkeypatch.setattr("builtins.input", lambda _: "42")
        assert inventory_module.prompt_int("Qty: ") == 42

    def test_blank_input_returns_default(self, inventory_module, monkeypatch):
        monkeypatch.setattr("builtins.input", lambda _: "")
        assert inventory_module.prompt_int("Qty: ", default=7) == 7

    def test_reprompts_on_non_integer_input(self, inventory_module, monkeypatch, capsys):
        responses = iter(["not a number", "5"])
        monkeypatch.setattr("builtins.input", lambda _: next(responses))
        assert inventory_module.prompt_int("Qty: ") == 5
        assert "whole number" in capsys.readouterr().out

    def test_reprompts_below_min_value(self, inventory_module, monkeypatch, capsys):
        responses = iter(["-1", "3"])
        monkeypatch.setattr("builtins.input", lambda _: next(responses))
        assert inventory_module.prompt_int("Qty: ", min_value=0) == 3
        assert ">= 0" in capsys.readouterr().out
