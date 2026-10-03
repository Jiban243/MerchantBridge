# MerchantBridge — WooCommerce MCP Connector

MerchantBridge is a read-only connector that exposes WooCommerce orders and product inventory as MCP tools.

Built for **Assignment 3: Build a private connector for a merchant tool** for the Razorpay Forward-Deployed Engineer, Agent Studio application.

## Problem Statement

An agent needs access to merchant data to answer operational questions accurately. Without a connector, a person must manually look up orders and inventory in WooCommerce and relay that information.

MerchantBridge provides authenticated, structured access to this data through a limited set of read-only tools.

Example questions the tools can help an agent answer:

- What is the status of this order?
- Which orders are pending payment?
- What items were included in an order?
- How much stock is available for a particular SKU?
- Which products are out of stock?

MerchantBridge supplies the data-access layer. It does not include an LLM or a conversational interface.

## Scope

The connector supports one configured WooCommerce store per server process.

It provides:

- Authentication using a WooCommerce consumer key and consumer secret.
- List, get, and search operations for orders and products.
- Product stock information and stock-status filtering.
- Pagination metadata.
- Bounded retries for rate limits and selected temporary server errors.
- An MCP server using standard input/output (`stdio`).
- A live-store verification script.

It does not create, update, or delete merchant records.

## Architecture

An MCP-compatible host starts the MerchantBridge server and calls its tools. The server validates inputs, calls the WooCommerce client, and returns structured results.

Credentials are configured on the server; they are not supplied as tool arguments.

| Component | Responsibility |
| --- | --- |
| `merchantbridge/client.py` | Authentication, input validation, WooCommerce requests, pagination, retries, and error handling |
| `merchantbridge/server.py` | MCP tool definitions and agent-facing response formatting |
| `merchantbridge/check_store.py` | Live WooCommerce read-only verification |
| `compose.yaml` | Local WordPress and MariaDB environment |
| `MCP_TOOLS.md` | Tool reference and capability limitations |

## MCP Tools

| Tool | Purpose |
| --- | --- |
| `list_orders` | List orders with pagination and optional status/date filters |
| `search_orders` | Search orders using WooCommerce search behavior |
| `get_order` | Retrieve one order by its ID |
| `list_products` | List products with pagination and optional stock-status filtering |
| `search_products` | Search products by text or SKU |
| `get_product` | Retrieve one product by its ID |

See [MCP_TOOLS.md](MCP_TOOLS.md) for further tool documentation.

Search results follow WooCommerce's search semantics; they are not semantic or vector search results.

## Prerequisites

- Python and `venv`.
- Docker Desktop with Docker Compose for the local demonstration.
- A WordPress installation with WooCommerce installed and activated.
- A WooCommerce REST API key with **Read** permissions.

The local demonstration was run using Python 3.14 and MCP Python SDK 1.30.0.

The server uses the MCP SDK 1.x `FastMCP` interface. Install the pinned dependencies from `requirements.txt`; upgrading to MCP 2.x requires code changes.

## Setup

### 1. Create a Python environment

From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

### 2. Configure the local environment

Create a `.env` file in the repository root:

```dotenv
DB_PASSWORD=replace_with_a_local_database_password
DB_ROOT_PASSWORD=replace_with_a_local_database_root_password

WC_BASE_URL=http://localhost:8080
WC_CONSUMER_KEY=
WC_CONSUMER_SECRET=
```

Replace the database placeholders before starting the containers.

The WooCommerce credentials will be generated after WooCommerce is installed.

Do not commit `.env` or share its contents.

### 3. Start WordPress and MariaDB

```bash
docker compose up -d
docker compose ps
```

Open:

```text
http://localhost:8080
```

Complete the WordPress installation, then install and activate the WooCommerce plugin.

The Compose environment starts WordPress and MariaDB. It does not automatically configure WooCommerce, generate API keys, or create demonstration records.

In WordPress, set **Settings → Permalinks → Post name** and save.

### 4. Generate a read-only WooCommerce API key

In the WordPress administration dashboard:

1. Open **WooCommerce → Settings → Advanced → REST API**.
2. Select **Add key**.
3. Give the key a descriptive name, such as `MerchantBridge`.
4. Select the appropriate WordPress user.
5. Set permissions to **Read**.
6. Generate the key.

Add the generated values to `.env`:

```dotenv
WC_BASE_URL=http://localhost:8080
WC_CONSUMER_KEY=replace_with_your_consumer_key
WC_CONSUMER_SECRET=replace_with_your_consumer_secret
```

Use a dedicated integration user with appropriate permissions where practical.

### 5. Create fictional demonstration data

Create sample products and orders through the WooCommerce dashboard.

The local demonstration used these products:

| Product | SKU | Price (INR) | Observed stock |
| --- | --- | ---: | ---: |
| MerchantBridge Wireless Mouse | `MB-MOUSE-001` | 799 | 24 |
| MerchantBridge USB Keyboard | `MB-KEYBOARD-001` | 1499 | 2 |
| MerchantBridge USB-C Hub | `MB-HUB-001` | 1999 | 0 |

Enable stock management for these products.

The demonstration also used three fictional orders:

| Order status | Items | Total (INR) |
| --- | --- | ---: |
| Pending payment | Wireless Mouse × 2 | 1598 |
| Processing | USB Keyboard × 1 | 1499 |
| Completed | Wireless Mouse × 1 | 799 |

WooCommerce may adjust stock when order statuses change. Check the resulting inventory before comparing demonstration output.

Record IDs are generated by WooCommerce and may differ between installations. Use fictional customer details only.

## Run the WooCommerce Verification

From the repository root, with the virtual environment active:

```bash
python -m merchantbridge.check_store
```

The script demonstrates:

- Order listing.
- Order search.
- Product listing and stock information.
- SKU search.
- Out-of-stock filtering.

A successful run ends with:

```text
Read-only check completed.
```

An empty result can be valid if the store has no matching records. To reproduce the sample search results, create the fictional demonstration data, including the `MB-MOUSE-001` SKU and customer names containing `Demo`.

## Run the MCP Server

```bash
python -m merchantbridge.server
```

The server uses `stdio`, not an HTTP endpoint. When started directly in a terminal, it waits for MCP messages and may produce no output.

Press `Ctrl+C` to stop it. A `KeyboardInterrupt` traceback may appear when stopping the process manually.

### Connect from an MCP host

Configure an MCP host that supports local stdio subprocesses with:

- **Executable:** the absolute path to `.venv/bin/python`.
- **Arguments:** `-m merchantbridge.server`.
- **Working directory:** the repository root.
- **Environment:** `WC_BASE_URL`, `WC_CONSUMER_KEY`, and `WC_CONSUMER_SECRET`.

The exact configuration format depends on the host. Supply credentials through its protected configuration or environment mechanism, not a committed configuration file.

Starting the server successfully is a startup check. It does not, by itself, verify MCP tool discovery or tool invocation.

## Authentication

For HTTPS stores, the client uses HTTP Basic authentication with the WooCommerce consumer key and secret.

For the local HTTP demonstration, the client uses OAuth 1.0a request signing. This is request authentication using existing WooCommerce credentials, not an interactive OAuth authorization flow.

Non-local HTTP URLs are rejected. Use HTTPS for a remote store.

## Rate-Limit and Error Handling

The client includes bounded retry handling for:

- `429` — Too Many Requests.
- `502` — Bad Gateway.
- `503` — Service Unavailable.
- `504` — Gateway Timeout.

Retry timing uses `Retry-After`, when available, or exponential backoff, subject to configured bounds.

The client also handles authentication failures, permission errors, missing records, invalid requests, and unexpected responses.

Rate-limit behavior depends on the WooCommerce deployment, hosting provider, and any proxy or security plugins. Successful requests to the local store do not prove that the retry paths have been exercised.

## Pagination

List and search operations return pagination metadata alongside results, including page information and totals.

An agent should request additional pages when needed. It must not treat a single page as the entire store or silently report partial results as complete.

## What an Agent Can Do

Using these tools, an agent can:

- Retrieve an order's recorded status, total, and line items.
- List orders using supported filters.
- Search for matching orders.
- Retrieve product details.
- Check recorded stock quantities and stock status.
- Search products by text or SKU.
- Identify out-of-stock products.

The agent should ground its answers in returned data and disclose errors or incomplete pagination.

## What an Agent Cannot Do

The connector does not expose tools to:

- Create, edit, or cancel orders.
- Issue refunds or collect payments.
- Update stock or prices.
- Modify customer records.
- Change store settings.
- Retrieve payment-gateway settlement information.
- Determine why a payment failed from an order status alone.
- Provide shipment tracking unless separately integrated.
- Access multiple stores within one configured server process.

A WooCommerce order status is not a substitute for payment-gateway or logistics data.

## Security

- The connector issues GET requests only.
- Use a WooCommerce API key with **Read** permissions.
- Credentials are not accepted as MCP tool arguments.
- Keep `.env` out of version control.
- Do not include credentials in screenshots, logs, or submitted files.
- Use fictional records for the demonstration.
- Returned order fields can contain customer information; read-only access does not make that data public.
- Restrict access to the MCP host and its tool results.
- For production, use HTTPS and managed secret storage.

The stdio server relies on the local host/process access boundary. It does not provide a separately authenticated, remotely hosted MCP endpoint.

## Verification Status

| Check | Status |
| --- | --- |
| Authentication against local WooCommerce | Verified |
| Order listing and search | Verified |
| Product listing and SKU search | Verified |
| Out-of-stock filtering | Verified |
| MCP SDK import and server startup | Verified |
| MCP client handshake, tool discovery, and invocation | Not yet verified |
| Individual get-by-ID operations | Not demonstrated by the recorded verification run |
| Rate-limit and retry failure scenarios | Not yet verified through simulated failures |
| Direct Razorpay Agent Studio integration | Not tested |

The assignment did not provide Razorpay Agent Studio access or connection instructions. This implementation supplies a standard MCP interface, but compatibility with Agent Studio's specific connection and deployment requirements remains unverified.

## Assumptions and Limitations

- The configured store exposes WooCommerce REST API v3.
- The API user and key have permission to read the requested resources.
- Search behavior is determined by WooCommerce and installed extensions.
- Inventory reflects WooCommerce's recorded state at request time; it is not a stock reservation.
- Unmanaged stock may have no numeric quantity and must not be interpreted as zero.
- Dedicated product-variation tools are not included.
- The connector does not maintain a synchronized local database.
- Multi-page reads are not a transactional snapshot; records can change between requests.
- The local Docker store and its records are not available to reviewers unless they reproduce the setup.
- Direct Agent Studio integration requires confirmation of its supported transport and configuration.

## Repository Hygiene

Ensure `.gitignore` includes:

```gitignore
.env
.venv/
__pycache__/
*.py[cod]
.pytest_cache/
```

Before submission, inspect the files being committed and confirm that no credentials or real customer data are included.

Ignoring a file does not remove it from Git if it was already tracked.

