from mcp.server.fastmcp import FastMCP

from .client import ConnectorError, WooCommerceClient


mcp = FastMCP("MerchantBridge WooCommerce")


def result(callable_function, *args, **kwargs):
    try:
        return {
            "ok": True,
            "data": callable_function(*args, **kwargs),
        }
    except ConnectorError as error:
        return {
            "ok": False,
            "error": error.as_dict(),
        }


def order_view(order):
    billing = order.get("billing") or {}

    return {
        "id": order.get("id"),
        "status": order.get("status"),
        "currency": order.get("currency"),
        "total": order.get("total"),
        "date_created": order.get("date_created"),
        "customer": {
            "first_name": billing.get("first_name"),
            "last_name": billing.get("last_name"),
            "email": billing.get("email"),
        },
        "items": [
            {
                "product_id": item.get("product_id"),
                "name": item.get("name"),
                "sku": item.get("sku"),
                "quantity": item.get("quantity"),
                "subtotal": item.get("subtotal"),
                "total": item.get("total"),
            }
            for item in order.get("line_items", [])
        ],
    }


def product_view(product):
    return {
        "id": product.get("id"),
        "name": product.get("name"),
        "sku": product.get("sku"),
        "price": product.get("price"),
        "stock_quantity": product.get("stock_quantity"),
        "stock_status": product.get("stock_status"),
        "manage_stock": product.get("manage_stock"),
        "type": product.get("type"),
        "permalink": product.get("permalink"),
    }


@mcp.tool()
def list_orders(
    page: int = 1,
    per_page: int = 20,
    status: str | None = None,
    after: str | None = None,
    before: str | None = None,
) -> dict:
    """List WooCommerce orders with optional status and date filters."""
    with WooCommerceClient.from_env() as client:
        output = result(
            client.list_orders,
            page=page,
            per_page=per_page,
            status=status,
            after=after,
            before=before,
        )

    if output["ok"]:
        output["data"]["items"] = [
            order_view(order) for order in output["data"]["items"]
        ]

    return output


@mcp.tool()
def search_orders(
    query: str,
    page: int = 1,
    per_page: int = 20,
) -> dict:
    """Search orders using WooCommerce's text search."""
    with WooCommerceClient.from_env() as client:
        output = result(
            client.search_orders,
            query,
            page=page,
            per_page=per_page,
        )

    if output["ok"]:
        output["data"]["items"] = [
            order_view(order) for order in output["data"]["items"]
        ]

    return output


@mcp.tool()
def get_order(order_id: int) -> dict:
    """Get one WooCommerce order by numeric ID."""
    with WooCommerceClient.from_env() as client:
        output = result(client.get_order, order_id)

    if output["ok"]:
        output["data"] = order_view(output["data"])

    return output


@mcp.tool()
def list_products(
    page: int = 1,
    per_page: int = 20,
    stock_status: str | None = None,
) -> dict:
    """List products and their current recorded inventory fields."""
    with WooCommerceClient.from_env() as client:
        output = result(
            client.list_products,
            page=page,
            per_page=per_page,
            stock_status=stock_status,
        )

    if output["ok"]:
        output["data"]["items"] = [
            product_view(product) for product in output["data"]["items"]
        ]

    return output


@mcp.tool()
def search_products(
    query: str | None = None,
    sku: str | None = None,
    page: int = 1,
    per_page: int = 20,
) -> dict:
    """Search products by text or exact SKU."""
    with WooCommerceClient.from_env() as client:
        output = result(
            client.search_products,
            query,
            sku=sku,
            page=page,
            per_page=per_page,
        )

    if output["ok"]:
        output["data"]["items"] = [
            product_view(product) for product in output["data"]["items"]
        ]

    return output


@mcp.tool()
def get_product(product_id: int) -> dict:
    """Get one product, including current recorded stock information."""
    with WooCommerceClient.from_env() as client:
        output = result(client.get_product, product_id)

    if output["ok"]:
        output["data"] = product_view(output["data"])

    return output


if __name__ == "__main__":
    mcp.run()
