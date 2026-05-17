"""Endpoint contract extraction tool.

Provides getEndpointContract tool for retrieving full endpoint specification.
"""

import logging
import copy
from typing import Any

logger = logging.getLogger("openapi-mcp.tools.contract")


def get_endpoint_contract(
    spec_store,
    path: str,
    method: str,
) -> dict[str, Any]:
    """
    Get full contract for an endpoint.

    Args:
        spec_store: SpecStore instance
        path: API path (e.g., "/users/{id}")
        method: HTTP method (GET, POST, etc.)

    Returns:
        Dict with complete endpoint specification including:
        - path, method, operationId, summary, description
        - parameters (query, path, header, cookie)
        - requestBody (if exists)
        - responses (with examples and headers)
        - tags, security, deprecated

    Raises:
        KeyError: If endpoint not found
    """

    if not spec_store.is_loaded():
        raise KeyError("Spec not loaded")

    logger.debug(f"Getting contract for {method.upper()} {path}")

    # Get the operation from spec_store
    try:
        operation = spec_store.get_endpoint(path, method)
    except KeyError as e:
        logger.error(f"Endpoint not found: {method.upper()} {path}")
        raise KeyError(f"Endpoint not found: {method.upper()} {path}") from e

    # Build contract from operation, preserving order and all fields
    contract = {
        "path": path,
        "method": method.upper(),
        "operationId": operation.get("operationId", f"{method.upper()} {path}"),
        "summary": operation.get("summary", ""),
        "description": operation.get("description", ""),
    }

    # Add parameters (path, query, header, cookie)
    if "parameters" in operation:
        contract["parameters"] = copy.deepcopy(operation["parameters"])
    else:
        contract["parameters"] = []

    # Add requestBody if exists
    if "requestBody" in operation:
        contract["requestBody"] = copy.deepcopy(operation["requestBody"])

    # Add responses (all status codes)
    if "responses" in operation:
        contract["responses"] = copy.deepcopy(operation["responses"])
    else:
        contract["responses"] = {}

    # Add tags if exists
    if "tags" in operation:
        contract["tags"] = operation["tags"]
    else:
        contract["tags"] = []

    # Add security if exists
    if "security" in operation:
        contract["security"] = copy.deepcopy(operation["security"])

    # Add deprecated flag
    contract["deprecated"] = operation.get("deprecated", False)

    logger.debug(f"Contract built: {len(contract)} fields")
    return contract
