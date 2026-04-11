"""Search tools for OpenAPI endpoints.

Provides searchEndpoints tool for finding endpoints by query, tags, and method.
"""

import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger("openapi-mcp.tools.search")


def search_endpoints(
    spec_store,
    query: Optional[str] = None,
    tags: Optional[List[str]] = None,
    method: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Search endpoints by query, tags, and HTTP method.

    Args:
        spec_store: SpecStore instance
        query: Substring to match in endpoint paths (case-insensitive)
        tags: List of tags to filter by (AND logic)
        method: HTTP method to filter by (GET, POST, etc.)

    Returns:
        List of matching endpoints with path, method, operationId, summary, tags
    """

    if not spec_store.is_loaded():
        logger.warning("Spec not loaded")
        return []

    spec = spec_store.get_spec()
    paths = spec.get("paths", {})

    logger.debug(f"Searching: query={query}, tags={tags}, method={method}")

    results = []

    for path, path_item in paths.items():
        # Check query filter
        if query is not None:
            if query.lower() not in path.lower():
                continue

        # Iterate through methods
        for http_method, operation in path_item.items():
            if http_method.lower() not in [
                "get",
                "post",
                "put",
                "delete",
                "patch",
                "head",
                "options",
            ]:
                continue

            # Check method filter
            if method is not None:
                if http_method.lower() != method.lower():
                    continue

            # Check tags filter
            if tags is not None:
                operation_tags = operation.get("tags", [])
                # Match if any of the requested tags are in operation tags
                if not any(tag in operation_tags for tag in tags):
                    continue

            # Add to results
            results.append(
                {
                    "path": path,
                    "method": http_method.upper(),
                    "operationId": operation.get(
                        "operationId", f"{http_method.upper()} {path}"
                    ),
                    "summary": operation.get("summary", ""),
                    "tags": operation.get("tags", []),
                }
            )

    # Sort by path for consistency
    results.sort(key=lambda x: x["path"])

    logger.debug(f"Found {len(results)} endpoints")
    return results
