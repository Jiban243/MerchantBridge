from .client import ConnectorError, WooCommerceClient


def main():
    try:
        with WooCommerceClient.from_env() as client:
            orders = client.list_orders(per_page=100)

            print("ORDERS")
            print("Total:", orders["total"])

            for order in orders["items"]:
                print(
                    f"#{order['id']} | "
                    f"{order['status']} | "
                    f"{order['currency']} {order['total']}"
                )

            print("\nORDER SEARCH")
            found_orders = client.search_orders("Demo")
            print([order["id"] for order in found_orders["items"]])

            print("\nPRODUCTS")
            products = client.list_products(per_page=100)
            print("Total:", products["total"])

            for product in products["items"]:
                print(
                    f"{product['sku']} | "
                    f"price={product['price']} | "
                    f"stock={product['stock_quantity']} | "
                    f"status={product['stock_status']}"
                )

            print("\nSKU SEARCH")
            mouse = client.search_products(sku="MB-MOUSE-001")
            print(
                [
                    {
                        "id": item["id"],
                        "name": item["name"],
                        "stock": item["stock_quantity"],
                    }
                    for item in mouse["items"]
                ]
            )

            print("\nOUT OF STOCK")
            out_of_stock = client.list_products(
                stock_status="outofstock",
            )
            print(
                [
                    {
                        "sku": item["sku"],
                        "name": item["name"],
                    }
                    for item in out_of_stock["items"]
                ]
            )

            print("\nRead-only check completed.")

    except ConnectorError as error:
        print(error.as_dict())
        raise SystemExit(1)


if __name__ == "__main__":
    main()
