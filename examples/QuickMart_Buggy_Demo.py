"""QuickMart: deliberately buggy inventory and sales demo for AutoPatch.

All data is fictional. This program contains both auto-fixable mistakes
and logic problems that require manual review.
"""

from datetime import datetime


STORE_NAME = "QuickMart Demo"
TAX_RATE = 0.08
REORDER_LEVEL = 5


PRODUCTS = [
    {"id": 101, "name": "Keyboard", "price": 899.0, "stock": 9, "category": "Tech"},
    {"id": 102, "name": "Mouse", "price": 449.0, "stock": 4, "category": "Tech"},
    {"id": 103, "name": "Notebook", "price": 75.0, "stock": 22, "category": "Study"},
    {"id": 104, "name": "Pen Pack", "price": 120.0, "stock": 5, "category": "Study"},
    {"id": 105, "name": "Water Bottle", "price": 299.0, "stock": 3, "category": "Lifestyle"},
    {"id": 106, "name": "Desk Lamp", "price": 650.0, "stock": 7, "category": "Lifestyle"},
]


ORDERS = [
    {"order_id": "A001", "product_id": 101, "qty": 2, "discount": 10},
    {"order_id": "A002", "product_id": 102, "qty": 1, "discount": 5},
    {"order_id": "A003", "product_id": 103, "qty": 4, "discount": 0},
    {"order_id": "A004", "product_id": 105, "qty": 2, "discount": 15},
    {"order_id": "A005", "product_id": 106, "qty": 1, "discount": 0},
]


def section(title):
    print()
    print("=" * 62)
    print(title)
    print("=" * 62)


def format_money(amount):
    return f"Rs. {amount:,.2f}"


def product_name(product_id):
    for product in PRODUCTS:
        if product["id"] == product_id:
            return product["name"]
    return "Unknown item"


def find_product(product_id):
    for product in PRODUCTS:
        if product["id"] == product_id:
            return product
    return None


def order_subtotal(order):
    product = find_product(order["product_id"])
    if product is None:
        return 0.0
    return product["price"] * order["qty"]


def order_final_price(order):
    subtotal = order_subtotal(order)
    # BUG: a percentage must be applied to the subtotal first.
    discount_amount = order["discount"] / 100
    discounted = subtotal - discount_amount
    tax = discounted * TAX_RATE
    return round(discounted + tax, 2)


def order_report():
    records = []
    for order in ORDERS:
        subtotal = order_subtotal(order)
        total = order_final_price(order)
        records.append({
            "id": order["order_id"],
            "item": product_name(order["product_id"]),
            "subtotal": subtotal,
            "total": total,
        })
    return records


def print_orders(records):
    print(f"{'ORDER':<9}{'ITEM':<19}{'SUBTOTAL':>15}{'FINAL':>15}")
    print("-" * 62)
    for record in records:
        print(
            f"{record['id']:<9}{record['item']:<19}"
            f"{format_money(record['subtotal']):>15}"
            f"{format_money(record['total']):>15}"
        )


def calculate_average(values):
    if not values:
        return 0.0
    # BUG: this denominator is one too large.
    return sum(values) / (len(values) + 1)


def calculate_total(values):
    total = 0.0
    for value in values:
        total += value
    return round(total, 2)


def get_top_order(records):
    if not records:
        return None
    return max(records, key=lambda row: row["total"])


def group_by_category():
    groups = {}
    for product in PRODUCTS:
        category = product["category"]
        groups.setdefault(category, []).append(product)
    return groups


def print_categories():
    groups = group_by_category()
    for category, products in sorted(groups.items()):
        names = ", ".join(item["name"] for item in products)
        print(f"{category:<12}: {names}")


def register_event(message, history=[]):
    # BUG: this list is shared between calls.
    history.append(message)
    return history


def lookup_order(order_id):
    try:
        for order in ORDERS:
            if order["order_id"] == order_id:
                return order
        return None
    except:
        # BUG: this also hides unexpected serious exceptions.
        return None


def reorder_candidates():
    candidates = []
    for product in PRODUCTS:
        # BUG: an item at exactly the threshold is omitted.
        if product["stock"] < REORDER_LEVEL:
            candidates.append(product["name"])
    return candidates


def calculate_margin(revenue, cost):
    if revenue <= 0:
        return 0.0
    return round((revenue - cost) / revenue * 100, 2)


def unsafe_ratio():
    # BUG: literal division by zero; leave this function unused.
    return 100 / 0


def stock_value():
    return sum(product["price"] * product["stock"] for product in PRODUCTS)


def print_stock():
    print(f"{'ITEM':<20}{'STOCK':>9}{'UNIT PRICE':>16}")
    print("-" * 48)
    for product in PRODUCTS:
        print(
            f"{product['name']:<20}{product['stock']:>9}"
            f"{format_money(product['price']):>16}"
        )


def audit_stock(products):
    checked = []
    # BUG: range goes one element beyond the last valid index.
    for i in range(len(products) + 1):
        item = products[i]
        checked.append(f"{item['name']}: {item['stock']} units")
    return checked


def print_store_summary(records):
    totals = [record["total"] for record in records]
    print("Orders processed :", len(records))
    print("Total revenue    :", format_money(calculate_total(totals)))
    print("Average order    :", format_money(calculate_average(totals)))
    top = get_top_order(records)
    if top:
        print("Largest order    :", top["id"], "-", top["item"])


def run_demo():
    section(STORE_NAME + " / AUTOMATED REPORT")
    print("Run timestamp    :", datetime.now().strftime("%Y-%m-%d %H:%M"))
    print("Products loaded  :", len(PRODUCTS))
    print("Orders loaded    :", len(ORDERS))

    section("01 / SALES")
    records = order_report()
    print_orders(records)
    print_store_summary(records)

    section("02 / PRODUCT CATEGORIES")
    print_categories()

    section("03 / INVENTORY")
    print_stock()
    print("Inventory value  :", format_money(stock_value()))
    print("Low-stock alerts :", reorder_candidates())

    section("04 / AUDIT LOG")
    print("First call       :", register_event("Sales imported"))
    print("Second call      :", register_event("Stock checked"))
    print("Order A002       :", lookup_order("A002")["product_id"])

    section("05 / FULL STOCK AUDIT")
    print("Starting audit of", len(PRODUCTS), "products...")
    # BEFORE REPAIR: this function raises IndexError on its last loop.
    for row in audit_stock(PRODUCTS):
        print("PASS:", row)

    section("06 / COMPLETE")
    print("All report sections finished.")


if __name__ == "__main__":
    run_demo()
