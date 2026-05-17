#!/usr/bin/env python3
"""
OpenAPI MCP Server

A FastMCP server that provides tools for working with OpenAPI specifications.
Tools help frontend developers generate TypeScript code, mocks, and tests from API specs.
"""

import logging
from pathlib import Path

try:
    # Preferred import path in modern MCP package versions.
    from mcp.server.fastmcp import FastMCP
except Exception:  # pragma: no cover - compatibility fallback
    # Fallback for legacy fastmcp package layouts.
    from fastmcp import FastMCP
from config import OPENAPI_SPEC_URL, MCP_PORT, LOG_LEVEL, SPEC_CACHE_PATH
from core.spec_loader import (
    load_spec_from_url,
    validate_spec,
    save_spec_to_cache,
    load_spec_from_cache,
)
from core.spec_store import get_store
from tools.search import search_endpoints
from tools.contract import get_endpoint_contract
from tools.schema_resolver import resolve_schema
from tools.codegen import CodeGenerator
from tools.mock_generator import generate_mock_data
from tools.validator import validate_request
from tools.auth import get_auth_info
from tools.debug_request import authenticated_debug_request

# Setup logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("openapi-mcp")

# Initialize FastMCP server
mcp = FastMCP("openapi-mcp")

# Placeholder for spec store (will be initialized in S2-S3)
spec_store = {"spec": None, "cached_path": Path(SPEC_CACHE_PATH)}


def get_health_status():
    """Return health status of the MCP server."""
    # FastMCP internals differ between versions. Prefer tool_manager API when available.
    tools_registered = 0
    try:
        if hasattr(mcp, "_tool_manager") and hasattr(mcp._tool_manager, "list_tools"):
            tools_registered = len(mcp._tool_manager.list_tools())
        elif hasattr(mcp, "_tools"):
            tools_registered = len(mcp._tools)
    except Exception:
        tools_registered = 0

    return {
        "status": "ok",
        "server": "openapi-mcp",
        "tools_registered": tools_registered,
        "spec_loaded": spec_store["spec"] is not None,
        "spec_url": OPENAPI_SPEC_URL,
    }


@mcp.tool()
def health_check() -> dict:
    """
    Check the health status of the MCP server.

    Returns:
        dict: Health status including number of tools and spec load status
    """
    return get_health_status()


@mcp.tool()
def searchEndpoints(
    query: str = None, tags: list[str] = None, method: str = None
) -> list[dict]:
    """
    Search endpoints by query, tags, and HTTP method.

    Args:
        query: Substring to match in endpoint paths (case-insensitive)
        tags: List of tags to filter by
        method: HTTP method to filter by (GET, POST, PUT, DELETE, PATCH, HEAD, OPTIONS)

    Returns:
        List of matching endpoints with path, method, operationId, summary, tags
    """
    spec_store_instance = get_store()
    return search_endpoints(spec_store_instance, query=query, tags=tags, method=method)


@mcp.tool()
def getEndpointContract(path: str, method: str) -> dict:
    """
    Get full contract for an endpoint.

    Args:
        path: API path (e.g., "/users/{id}")
        method: HTTP method (GET, POST, PUT, DELETE, PATCH, HEAD, OPTIONS)

    Returns:
        Dict with complete endpoint specification including parameters, requestBody, responses

    Raises:
        KeyError: If endpoint not found
    """
    spec_store_instance = get_store()
    return get_endpoint_contract(spec_store_instance, path=path, method=method)


@mcp.tool()
def resolveSchema(schema_name: str) -> dict:
    """
    Resolve a schema by expanding all $ref references recursively.

    Args:
        schema_name: Schema name (e.g., "User") or full $ref (e.g., "#/components/schemas/User")

    Returns:
        Dict with schema definition, all $ref expanded recursively

    Raises:
        KeyError: If schema not found
        RuntimeError: If max recursion depth exceeded
    """
    spec_store_instance = get_store()
    return resolve_schema(spec_store_instance, schema_name=schema_name)


@mcp.tool()
def generateClient(
    endpoint_ids: list[int], language: str = "typescript", include: list[str] = None
) -> str:
    """
    Generate TypeScript client code for a list of endpoints.

    Args:
        endpoint_ids: List of endpoint path/method tuples to generate code for
        language: Target language (only "typescript" supported in MVP)
        include: What to include ["types", "fetch"] - defaults to both

    Returns:
        Ready-to-paste TypeScript code with types and fetch functions
    """
    if include is None:
        include = ["types", "fetch"]

    spec_store_instance = get_store()
    codegen = CodeGenerator(spec_store_instance)
    return codegen.generate_client(
        endpoint_ids=endpoint_ids, language=language, include=include
    )


@mcp.tool()
def generateMockData(schema_name: str, count: int = 1) -> dict:
    """
    Generate realistic mock data for a JSON schema.

    Args:
        schema_name: Schema name or $ref (e.g., "User", "#/components/schemas/User")
        count: Number of mock instances to generate (default: 1)

    Returns:
        dict: {"success": true, "data": [mock_objects]} or {"success": false, "error": "..."}
    """
    return generate_mock_data(schema_name=schema_name, count=count)


@mcp.tool()
def validateRequest(path: str, method: str, data: dict) -> dict:
    """
    Validate request data against endpoint contract.

    Args:
        path: API path (e.g., "/users/{id}")
        method: HTTP method (GET, POST, PUT, DELETE, PATCH, HEAD, OPTIONS)
        data: Request data to validate

    Returns:
        {
            "valid": bool,
            "errors": [
                {
                    "path": "field.name[0]",
                    "message": "error description"
                }
            ]
        }
    """
    return validate_request(path=path, method=method, data=data)


@mcp.tool()
def getAuthInfo() -> dict:
    """
    Extract authentication requirements from OpenAPI spec.

    Returns:
        {
            "required": bool,
            "global": {
                "required": bool,
                "schemes": ["scheme_name"]
            },
            "schemes": [
                {
                    "name": "api_key",
                    "type": "apiKey|http|oauth2|openIdConnect",
                    "in": "header|query|cookie",
                    "paramName": "X-API-Key",
                    "scheme": "bearer|basic",
                    "bearerFormat": "JWT",
                    "scopes": ["read:users"]
                }
            ],
            "endpoints": {
                "/users": {
                    "overrides": bool,
                    "required": bool,
                    "schemes": ["bearer"]
                }
            }
        }
    """
    return get_auth_info()


@mcp.tool()
def authenticatedDebugRequest(
    path: str,
    method: str,
    query: dict | None = None,
    body: dict | None = None,
    headers: dict | None = None,
    auth: bool = True,
    auth_user: str | None = None,
    auth_role: str | None = None,
) -> dict:
    """
    Execute a live debug request against the target API.
    """
    return authenticated_debug_request(
        path=path,
        method=method,
        query=query,
        body=body,
        headers=headers,
        auth=auth,
        auth_user=auth_user,
        auth_role=auth_role,
    )


@mcp.tool()
def generateTests(
    endpoint_ids: list,
    framework: str = "jest",
    include_mocks: bool = True,
) -> str:
    """
    Generate Jest tests for list of endpoints.

    Args:
        endpoint_ids: List of endpoint IDs to generate tests for
        framework: Test framework (only 'jest' supported)
        include_mocks: Whether to include mock data in tests

    Returns:
        Ready-to-run Jest test code as string
    """
    spec_store_instance = get_store()
    codegen = CodeGenerator(spec_store_instance)
    return codegen.generate_tests(
        endpoint_ids=endpoint_ids,
        framework=framework,
        include_mocks=include_mocks,
    )


def main():
    """Main entry point for the MCP server."""

    logger.info("=" * 60)
    logger.info("OpenAPI MCP Server starting...")
    logger.info(f"OPENAPI_SPEC_URL: {OPENAPI_SPEC_URL}")
    logger.info(f"MCP_PORT: {MCP_PORT}")
    logger.info(f"LOG_LEVEL: {LOG_LEVEL}")
    logger.info(f"SPEC_CACHE_PATH: {SPEC_CACHE_PATH}")
    logger.info("=" * 60)

    # Initialize spec loading (S2)
    spec = None
    spec_store_instance = get_store()

    try:
        logger.info("Attempting to load spec from URL...")
        spec = load_spec_from_url(OPENAPI_SPEC_URL)
        validate_spec(spec)
        save_spec_to_cache(spec, Path(SPEC_CACHE_PATH))
        spec_store_instance.set_spec(spec)
        spec_store["spec"] = spec
        logger.info("✓ Spec loaded successfully")

    except Exception as e:
        logger.warning(f"Failed to load spec from URL: {str(e)}")

        # Try to fallback to cache
        try:
            logger.info("Attempting to load spec from cache...")
            spec = load_spec_from_cache(Path(SPEC_CACHE_PATH))
            if spec:
                validate_spec(spec)
                spec_store_instance.set_spec(spec)
                spec_store["spec"] = spec
                logger.info("✓ Spec loaded from cache")
            else:
                logger.error("No cached spec available")
        except Exception as cache_error:
            logger.error(f"Failed to load cached spec: {str(cache_error)}")

    # Log health status
    health = get_health_status()
    logger.info(f"MCP server initialized with {health['tools_registered']} tools")
    logger.info(f"Spec loaded: {health['spec_loaded']}")

    logger.info("=" * 60)
    logger.info("Waiting for MCP connections...")
    logger.info("=" * 60)

    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
