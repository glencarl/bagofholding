#!/usr/bin/env python3
"""
Supply Inventory Manager
-------------------------
A simple command-line tool to track supplies: add, update, remove,
search, and list items. Data is stored in a local JSON file so it
persists between runs.

Usage:
    python inventory.py

Data file:
    inventory_data.json (created automatically in the same folder).
    Override with the INVENTORY_DATA_FILE environment variable.
"""

import json
import os
import tempfile
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.environ.get("INVENTORY_DATA_FILE", os.path.join(BASE_DIR, "inventory_data.json"))

# Fields every item is expected to have, and the default used when a record
# on disk is missing one (e.g. hand-edited data or an older schema version).
ITEM_DEFAULTS = {
    "name": "",
    "quantity": 0,
    "unit": "",
    "category": "general",
    "location": "",
    "low_stock_threshold": 0,
    "last_updated": "",
}


# ---------------------------------------------------------------------------
# Data handling
# ---------------------------------------------------------------------------

def load_inventory():
    """Load inventory from the JSON file, or return an empty dict if none exists."""
    if not os.path.exists(DATA_FILE):
        return {}
    try:
        with open(DATA_FILE, "r") as f:
            raw = json.load(f)
    except (json.JSONDecodeError, IOError) as exc:
        print(f"Warning: could not read {DATA_FILE} ({exc}); starting with an empty inventory.")
        return {}

    if not isinstance(raw, dict):
        print(f"Warning: {DATA_FILE} did not contain the expected data; starting with an empty inventory.")
        return {}

    # Backfill any missing fields so older/hand-edited records can't crash
    # later lookups (this is what caused the low-stock alerts to silently
    # break for items missing "low_stock_threshold").
    for item in raw.values():
        for field, default in ITEM_DEFAULTS.items():
            item.setdefault(field, default)
    return raw


def save_inventory(inventory):
    """Save the inventory dict to the JSON file, atomically."""
    directory = os.path.dirname(DATA_FILE) or "."
    fd, tmp_path = tempfile.mkstemp(prefix=".inventory_data-", suffix=".json", dir=directory)
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(inventory, f, indent=2)
        os.replace(tmp_path, DATA_FILE)
    except Exception:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise


# ---------------------------------------------------------------------------
# Core operations
# ---------------------------------------------------------------------------

def add_item(inventory, name, quantity, category="general", location="", unit="", low_stock_threshold=0):
    """Add a new item or, if it already exists, add to its quantity."""
    key = name.strip().lower()
    if key in inventory:
        inventory[key]["quantity"] += quantity
        inventory[key]["last_updated"] = datetime.now().isoformat(timespec="seconds")
        print(f"Updated '{name}': quantity is now {inventory[key]['quantity']}.")
    else:
        inventory[key] = {
            "name": name.strip(),
            "quantity": quantity,
            "unit": unit,
            "category": category.strip().lower(),
            "location": location.strip(),
            "low_stock_threshold": low_stock_threshold,
            "last_updated": datetime.now().isoformat(timespec="seconds"),
        }
        print(f"Added '{name}' (quantity: {quantity}).")
    save_inventory(inventory)


def remove_item(inventory, name, quantity=None):
    """Remove an item entirely, or reduce its quantity if a quantity is given."""
    key = name.strip().lower()
    if key not in inventory:
        print(f"'{name}' not found in inventory.")
        return

    if quantity is None:
        del inventory[key]
        print(f"Removed '{name}' entirely from inventory.")
    else:
        inventory[key]["quantity"] -= quantity
        inventory[key]["last_updated"] = datetime.now().isoformat(timespec="seconds")
        if inventory[key]["quantity"] <= 0:
            del inventory[key]
            print(f"'{name}' quantity reached zero and was removed.")
        else:
            print(f"Removed {quantity} of '{name}'. Remaining: {inventory[key]['quantity']}.")
    save_inventory(inventory)


def update_item(inventory, name, **fields):
    """Update arbitrary fields (location, category, unit, low_stock_threshold, quantity)."""
    key = name.strip().lower()
    if key not in inventory:
        print(f"'{name}' not found in inventory.")
        return
    for field, value in fields.items():
        if value is not None and field in inventory[key]:
            inventory[key][field] = value
    inventory[key]["last_updated"] = datetime.now().isoformat(timespec="seconds")
    save_inventory(inventory)
    print(f"Updated '{name}'.")


def search_items(inventory, term):
    """Search by name, category, or location (case-insensitive substring match)."""
    term = term.strip().lower()
    results = [
        item for item in inventory.values()
        if term in item.get("name", "").lower()
        or term in item.get("category", "").lower()
        or term in item.get("location", "").lower()
    ]
    return results


def low_stock_items(inventory):
    """Return items at or below their low-stock threshold (threshold > 0)."""
    return [
        item for item in inventory.values()
        if item.get("low_stock_threshold", 0) > 0
        and item.get("quantity", 0) <= item["low_stock_threshold"]
    ]


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------

def print_table(items):
    if not items:
        print("No items to display.")
        return

    headers = ["Name", "Qty", "Unit", "Category", "Location", "Last Updated"]
    rows = [
        [
            it.get("name", ""),
            str(it.get("quantity", 0)),
            it.get("unit", ""),
            it.get("category", ""),
            it.get("location", ""),
            it.get("last_updated", "")[:16].replace("T", " "),
        ]
        for it in sorted(items, key=lambda x: x.get("name", "").lower())
    ]

    widths = [max(len(h), max((len(r[i]) for r in rows), default=0)) for i, h in enumerate(headers)]
    line = "  ".join(h.ljust(widths[i]) for i, h in enumerate(headers))
    print(line)
    print("-" * len(line))
    for r in rows:
        print("  ".join(r[i].ljust(widths[i]) for i in range(len(headers))))


def print_summary(inventory):
    print(f"\nTotal distinct items: {len(inventory)}")
    total_qty = sum(it.get("quantity", 0) for it in inventory.values())
    print(f"Total quantity across all items: {total_qty}")
    categories = sorted({it.get("category", "general") for it in inventory.values()})
    if categories:
        print(f"Categories: {', '.join(categories)}")


# ---------------------------------------------------------------------------
# Interactive menu
# ---------------------------------------------------------------------------

def prompt_int(prompt_text, default=None, min_value=None):
    """Prompt for an integer, re-asking on bad input instead of recursing."""
    while True:
        raw = input(prompt_text).strip()
        if raw == "" and default is not None:
            return default
        try:
            value = int(raw)
        except ValueError:
            print("Please enter a whole number.")
            continue
        if min_value is not None and value < min_value:
            print(f"Please enter a number >= {min_value}.")
            continue
        return value


def main():
    inventory = load_inventory()

    menu = """
==== Supply Inventory Manager ====
1. Add item / add stock
2. Remove item / reduce stock
3. Update item details
4. List all items
5. Search items
6. Show low-stock items
7. Show summary
8. Exit
"""

    while True:
        print(menu)
        choice = input("Choose an option (1-8): ").strip()

        if choice == "1":
            name = input("Item name: ").strip()
            if not name:
                print("Name cannot be empty.")
                continue
            qty = prompt_int("Quantity to add: ", min_value=1)
            unit = input("Unit (e.g. boxes, ft, ea) [optional]: ").strip()
            category = input("Category [optional, default 'general']: ").strip() or "general"
            location = input("Location [optional]: ").strip()
            threshold = prompt_int("Low-stock alert threshold (0 for none): ", default=0, min_value=0)
            add_item(inventory, name, qty, category, location, unit, threshold)

        elif choice == "2":
            name = input("Item name to remove/reduce: ").strip()
            if not name:
                print("Name cannot be empty.")
                continue
            mode = input("Remove (a)ll of this item or (r)educe by amount? [a/r]: ").strip().lower()
            if mode == "r":
                qty = prompt_int("Quantity to remove: ", min_value=1)
                remove_item(inventory, name, qty)
            else:
                remove_item(inventory, name)

        elif choice == "3":
            name = input("Item name to update: ").strip()
            if not name:
                print("Name cannot be empty.")
                continue
            print("Leave a field blank to keep it unchanged.")
            location = input("New location: ").strip() or None
            category = input("New category: ").strip() or None
            unit = input("New unit: ").strip() or None
            threshold_raw = input("New low-stock threshold: ").strip()
            threshold = int(threshold_raw) if threshold_raw.isdigit() else None
            update_item(inventory, name, location=location, category=category,
                        unit=unit, low_stock_threshold=threshold)

        elif choice == "4":
            print_table(list(inventory.values()))

        elif choice == "5":
            term = input("Search term (matches name, category, or location): ").strip()
            print_table(search_items(inventory, term))

        elif choice == "6":
            items = low_stock_items(inventory)
            if items:
                print("\nLow-stock items:")
                print_table(items)
            else:
                print("No items are currently low on stock.")

        elif choice == "7":
            print_summary(inventory)

        elif choice == "8":
            print("Goodbye!")
            break

        else:
            print("Invalid choice, please enter a number from 1-8.")


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print("\nGoodbye!")
