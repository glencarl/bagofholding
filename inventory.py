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
    inventory_data.json (created automatically in the same folder)
"""

import json
import os
from datetime import datetime

DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "inventory_data.json")


# ---------------------------------------------------------------------------
# Data handling
# ---------------------------------------------------------------------------

def load_inventory():
    """Load inventory from the JSON file, or return an empty dict if none exists."""
    if not os.path.exists(DATA_FILE):
        return {}
    try:
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        print(f"Warning: could not read {DATA_FILE}, starting with an empty inventory.")
        return {}


def save_inventory(inventory):
    """Save the inventory dict to the JSON file."""
    with open(DATA_FILE, "w") as f:
        json.dump(inventory, f, indent=2)


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
        if term in item["name"].lower()
        or term in item["category"].lower()
        or term in item["location"].lower()
    ]
    return results


def low_stock_items(inventory):
    """Return items at or below their low-stock threshold (threshold > 0)."""
    return [
        item for item in inventory.values()
        if item["low_stock_threshold"] > 0 and item["quantity"] <= item["low_stock_threshold"]
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
            it["name"],
            str(it["quantity"]),
            it["unit"],
            it["category"],
            it["location"],
            it["last_updated"][:16].replace("T", " "),
        ]
        for it in sorted(items, key=lambda x: x["name"].lower())
    ]

    widths = [max(len(h), max((len(r[i]) for r in rows), default=0)) for i, h in enumerate(headers)]
    line = "  ".join(h.ljust(widths[i]) for i, h in enumerate(headers))
    print(line)
    print("-" * len(line))
    for r in rows:
        print("  ".join(r[i].ljust(widths[i]) for i in range(len(headers))))


def print_summary(inventory):
    print(f"\nTotal distinct items: {len(inventory)}")
    total_qty = sum(it["quantity"] for it in inventory.values())
    print(f"Total quantity across all items: {total_qty}")
    categories = sorted(set(it["category"] for it in inventory.values()))
    if categories:
        print(f"Categories: {', '.join(categories)}")


# ---------------------------------------------------------------------------
# Interactive menu
# ---------------------------------------------------------------------------

def prompt_int(prompt_text, default=None):
    raw = input(prompt_text).strip()
    if raw == "" and default is not None:
        return default
    try:
        return int(raw)
    except ValueError:
        print("Please enter a whole number.")
        return prompt_int(prompt_text, default)


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
            qty = prompt_int("Quantity to add: ")
            unit = input("Unit (e.g. boxes, ft, ea) [optional]: ").strip()
            category = input("Category [optional, default 'general']: ").strip() or "general"
            location = input("Location [optional]: ").strip()
            threshold = prompt_int("Low-stock alert threshold (0 for none): ", default=0)
            add_item(inventory, name, qty, category, location, unit, threshold)

        elif choice == "2":
            name = input("Item name to remove/reduce: ").strip()
            mode = input("Remove (a)ll of this item or (r)educe by amount? [a/r]: ").strip().lower()
            if mode == "r":
                qty = prompt_int("Quantity to remove: ")
                remove_item(inventory, name, qty)
            else:
                remove_item(inventory, name)

        elif choice == "3":
            name = input("Item name to update: ").strip()
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
    main()