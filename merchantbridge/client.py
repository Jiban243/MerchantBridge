from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit

import requests
from dotenv import dotenv_values
from requests.auth import HTTPBasicAuth
from requests_oauthlib import OAuth1


class ConnectorError(Exception):
    def __init__(self, code: str, message: str, status=None, retry_after=None):
        super().__init__(message)
        self.code = code
        self.status = status
        self.retry_after = retry_after

    def as_dict(self):
        return {
            "code": self.code,
            "message": str(self),
            "status": self.status,
            "retry_after": self.retry_after,
        }


def positive_int(value, field, maximum=None):
    if type(value) is not int or value < 1:
        raise ConnectorError("invalid_input", f"{field} must be a positive integer.")
    if maximum is not None and value > maximum:
        raise ConnectorError("invalid_input", f"{field} must be at most {maximum}.")
    return value


def valid_text(value, field):
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > 200:
        raise ConnectorError("invalid_input", f"{field} must contain 1–200 characters.")
    return value.strip()


class WooCommerceClient:
    def __init__(
        self,
        base_url,
        consumer_key,
        consumer_secret,
        *,
        session=None,
        sleep=time.sleep,
        max_retries=2,
        max_wait=10,
    ):
        parsed = urlsplit(base_url)

        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            raise ConnectorError("configuration", "Invalid WC_BASE_URL.")

        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ConnectorError("configuration", "WC_BASE_URL must not contain credentials or query parameters.")

        if parsed.scheme == "http" and parsed.hostname not in (
            "localhost",
            "127.0.0.1",
            "::1",
        ):
            raise ConnectorError(
                "configuration",
                "HTTP is allowed only for the local demo store. Use HTTPS remotely.",
            )

        if not consumer_key or not consumer_secret:
            raise ConnectorError("configuration", "WooCommerce credentials are missing.")

        self.api_base = base_url.rstrip("/") + "/wp-json/wc/v3"
        self.consumer_key = consumer_key
        self.consumer_secret = consumer_secret
        self.https = parsed.scheme == "https"

        self.session = session or requests.Session()
        self.session.trust_env = False

        self.sleep = sleep
        self.max_retries = positive_int(max_retries, "max_retries", 5)
        self.max_wait = positive_int(max_wait, "max_wait", 60)

    @classmethod
    def from_env(cls, env_file=".env", **kwargs):
        values = {**dotenv_values(env_file), **os.environ}

        return cls(
            values.get("WC_BASE_URL", ""),
            values.get("WC_CONSUMER_KEY", ""),
            values.get("WC_CONSUMER_SECRET", ""),
            **kwargs,
        )

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.session.close()

    def _auth(self):
        if self.https:
            return HTTPBasicAuth(self.consumer_key, self.consumer_secret)

        return OAuth1(
            self.consumer_key,
            client_secret=self.consumer_secret,
            signature_method="HMAC-SHA1",
        )

    def _retry_delay(self, retry_after, attempt):
        if retry_after:
            try:
                if retry_after.strip().isdigit():
                    return int(retry_after)

                date = parsedate_to_datetime(retry_after)

                if date.tzinfo is None:
                    date = date.replace(tzinfo=timezone.utc)

                return max(
                    0,
                    int((date - datetime.now(timezone.utc)).total_seconds()),
                )
            except (ValueError, TypeError, OverflowError):
                pass

        return min(2**attempt, self.max_wait)

    def _request(self, resource, record_id=None, params=None):
        if resource not in ("orders", "products"):
            raise ConnectorError("invalid_input", "Unsupported resource.")

        path = resource

        if record_id is not None:
            record_id = positive_int(record_id, "record_id")
            path += f"/{record_id}"

        url = f"{self.api_base}/{path}"

        for attempt in range(self.max_retries + 1):
            try:
                response = self.session.get(
                    url,
                    params=params,
                    auth=self._auth(),
                    timeout=(5, 20),
                    allow_redirects=False,
                )
            except requests.Timeout:
                if attempt < self.max_retries:
                    self.sleep(min(2**attempt, self.max_wait))
                    continue

                raise ConnectorError(
                    "connection_failed",
                    "WooCommerce request timed out after bounded retries.",
                ) from None
            except requests.ConnectionError:
                if attempt < self.max_retries:
                    self.sleep(min(2**attempt, self.max_wait))
                    continue

                raise ConnectorError(
                    "connection_failed",
                    "Could not connect to WooCommerce after bounded retries.",
                ) from None
            except requests.RequestException:
                raise ConnectorError(
                    "request_failed",
                    "WooCommerce request failed.",
                ) from None

            status = response.status_code

            if status in (429, 502, 503, 504):
                delay = self._retry_delay(
                    response.headers.get("Retry-After"),
                    attempt,
                )
                response.close()

                if attempt < self.max_retries and delay <= self.max_wait:
                    self.sleep(delay)
                    continue

                if status == 429:
                    raise ConnectorError(
                        "rate_limited",
                        "WooCommerce rate limit reached. Retry later.",
                        status=status,
                        retry_after=delay,
                    )

                raise ConnectorError(
                    "store_unavailable",
                    "WooCommerce is temporarily unavailable.",
                    status=status,
                    retry_after=delay,
                )

            if status != 200:
                response.close()

                errors = {
                    400: ("invalid_request", "WooCommerce rejected the request."),
                    401: ("authentication_failed", "Check the WooCommerce credentials."),
                    403: ("permission_denied", "The API key lacks read permission."),
                    404: ("not_found", "The requested record was not found."),
                }

                if 300 <= status < 400:
                    code, message = (
                        "redirect_blocked",
                        "Check the configured canonical store URL.",
                    )
                else:
                    code, message = errors.get(
                        status,
                        ("upstream_error", "WooCommerce returned an unexpected status."),
                    )

                raise ConnectorError(code, message, status=status)

            try:
                data = response.json()
                headers = dict(response.headers)
            except ValueError:
                raise ConnectorError(
                    "invalid_response",
                    "WooCommerce returned invalid JSON.",
                ) from None
            finally:
                response.close()

            if record_id is None:
                if not isinstance(data, list) or any(
                    not isinstance(item, dict) for item in data
                ):
                    raise ConnectorError(
                        "invalid_response",
                        "WooCommerce returned an unexpected list response.",
                    )
            elif not isinstance(data, dict):
                raise ConnectorError(
                    "invalid_response",
                    "WooCommerce returned an unexpected record response.",
                )

            return data, headers

        raise ConnectorError("request_failed", "Request failed.")

    def _list(self, resource, page, per_page, filters):
        positive_int(page, "page")
        positive_int(per_page, "per_page", 100)

        params = {
            "page": page,
            "per_page": per_page,
            "orderby": "id",
            "order": "asc",
            **filters,
        }

        items, headers = self._request(resource, params=params)

        try:
            total = int(headers.get("X-WP-Total"))
        except (TypeError, ValueError):
            total = None

        try:
            total_pages = int(headers.get("X-WP-TotalPages"))
        except (TypeError, ValueError):
            total_pages = None

        has_more = None
        next_page = None

        if total_pages is not None:
            has_more = page < total_pages

            if has_more:
                next_page = page + 1

        return {
            "items": items,
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": total_pages,
            "has_more": has_more,
            "next_page": next_page,
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
        }

    def list_orders(
        self,
        *,
        page=1,
        per_page=20,
        status=None,
        after=None,
        before=None,
    ):
        filters = {}

        if status is not None:
            allowed = {
                "pending",
                "processing",
                "on-hold",
                "completed",
                "cancelled",
                "refunded",
                "failed",
                "any",
            }

            if status not in allowed:
                raise ConnectorError("invalid_input", "Unsupported order status.")

            filters["status"] = status

        dates = {}

        for field, value in (("after", after), ("before", before)):
            if value is None:
                continue

            try:
                dt = datetime.fromisoformat(value.replace("Z", "+00:00"))

                if dt.tzinfo is None:
                    raise ValueError

                filters[field] = (
                    dt.astimezone(timezone.utc)
                    .isoformat()
                    .replace("+00:00", "Z")
                )
                dates[field] = dt
            except (ValueError, TypeError):
                raise ConnectorError(
                    "invalid_input",
                    f"{field} must be an ISO 8601 timestamp with timezone.",
                ) from None

        if dates.get("after") and dates.get("before"):
            if dates["after"] >= dates["before"]:
                raise ConnectorError(
                    "invalid_input",
                    "after must be earlier than before.",
                )

        if dates:
            filters["dates_are_gmt"] = "true"

        return self._list("orders", page, per_page, filters)

    def search_orders(self, query, *, page=1, per_page=20):
        return self._list(
            "orders",
            page,
            per_page,
            {"search": valid_text(query, "query")},
        )

    def get_order(self, order_id):
        return self._request("orders", order_id)[0]

    def list_products(self, *, page=1, per_page=20, stock_status=None):
        filters = {}

        if stock_status is not None:
            allowed = {"instock", "outofstock", "onbackorder"}

            if stock_status not in allowed:
                raise ConnectorError(
                    "invalid_input",
                    "Unsupported stock status.",
                )

            filters["stock_status"] = stock_status

        return self._list("products", page, per_page, filters)

    def search_products(
        self,
        query=None,
        *,
        sku=None,
        page=1,
        per_page=20,
    ):
        if (query is None) == (sku is None):
            raise ConnectorError(
                "invalid_input",
                "Provide exactly one of query or sku.",
            )

        if sku is not None:
            filters = {"sku": valid_text(sku, "sku")}
        else:
            filters = {"search": valid_text(query, "query")}

        return self._list("products", page, per_page, filters)

    def get_product(self, product_id):
        return self._request("products", product_id)[0]
