# MerchantBridge MCP tools

MerchantBridge exposes six read-only tools:

| Tool | Purpose |
|---|---|
| `list_orders` | List orders with pagination, status, and date filters |
| `search_orders` | Search orders using WooCommerce text search |
| `get_order` | Retrieve one order by numeric ID |
| `list_products` | List products and recorded stock information |
| `search_products` | Search products by text or exact SKU |
| `get_product` | Retrieve one product and its current recorded stock |

The connector uses the existing WooCommerce read-only API key.

It does not create, update, cancel, refund, or delete anything.

The agent must not infer delivery dates, delay causes, or inventory quantities when
WooCommerce returns a missing quantity. Search results may contain multiple
matches, so the agent should ask the merchant to clarify when necessary.

Pagination metadata is returned with every list/search operation. A response with
`has_more=true` is incomplete until the next page is retrieved.

The MCP server has not been tested inside Razorpay Agent Studio because the
assignment did not provide Agent Studio access or connection instructions.
