"""Bounded diagnostic metadata; never serialize raw transport exceptions."""
import re

import requests
from pydantic import ValidationError


class ScraperFailure(ValueError):
    def __init__(self, message, category, detail=None, stage="fetch"):
        super().__init__(message)
        self.category = category
        self.detail = detail or message
        self.stage = stage


def request_failure(error):
    # Inspect internally, but only publish allowlisted tokens/static descriptions.
    text = str(error).lower()
    if "10054" in text or "connection reset" in text or "forcibly closed" in text:
        return "connection_reset", "HTTP connection reset by peer (connection reset / Windows 10054)."
    if isinstance(error, requests.Timeout):
        return "request_timeout", "HTTP request exceeded its configured connect/read timeout."
    return "dns_or_connection_error", "HTTP connection, DNS, TLS or proxy connection failed."


def browser_failure(error, operation):
    text = str(error)
    if "closed" in text.lower():
        return "page_closed", "Browser, context or page closed during " + operation + "."
    if operation == "launch":
        return "browser_launch_error", "Chrome initialization failed."
    if operation == "navigation" and ("timeout" in type(error).__name__.lower() or "timeout" in text.lower()):
        return "browser_navigation_timeout", "Chrome navigation exceeded its configured timeout."
    # Only known network codes can leave this boundary, never URLs or call logs.
    codes = {"ERR_HTTP2_PROTOCOL_ERROR", "ERR_CONNECTION_RESET", "ERR_NAME_NOT_RESOLVED",
             "ERR_CONNECTION_CLOSED", "ERR_CONNECTION_REFUSED", "ERR_INTERNET_DISCONNECTED",
             "ERR_TIMED_OUT", "ERR_CERT_AUTHORITY_INVALID", "ERR_ABORTED"}
    token = next((code for code in re.findall(r"\bERR_[A-Z0-9_]+\b", text) if code in codes), None)
    return "browser_navigation_error" if operation == "navigation" else "browser_page_error", (
        "Chrome " + operation + " failed" + (": " + token if token else "") + ".")


def failure_metadata(error, stage):
    if isinstance(error, ScraperFailure):
        return dict(failure_stage=error.stage, failure_category=error.category, failure_detail=error.detail)
    category = {"before_fetch": "invalid_input", "fetch": "fetch_failed",
                "extraction": "extraction_failed", "validation": "validation_failed"}.get(stage, "local_io_error")
    # Source/validation error text may include untrusted values. Keep detail static.
    return dict(failure_stage=stage, failure_category=category,
                failure_detail={"before_fetch": "Input could not be prepared for fetching.",
                                "fetch": "Could not obtain a usable product page.",
                                "extraction": "Product extraction rejected the retrieved page.",
                                "validation": "Required product fields failed validation."}.get(stage, "Local HTML I/O failed."))


def should_browser_fallback(error, stage, candidate=None):
    """Only recover retrieval/incomplete-data failures, never identity or bad data."""
    if stage == "before_fetch":
        return False
    if isinstance(error, ScraperFailure):
        return error.category in {"connection_reset", "request_timeout", "dns_or_connection_error",
                                  "fetch_failed", "extraction_failed", "source_data_unavailable"}
    if isinstance(error, ValidationError):
        issues = error.errors()
        return bool(issues) and all(issue["loc"] in {("title",), ("price",), ("currency",)}
                                    and (candidate or {}).get(issue["loc"][0]) in (None, "") for issue in issues)
    return isinstance(error, ValueError) and stage in {"fetch", "extraction"}
