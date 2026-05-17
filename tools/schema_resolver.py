"""Schema resolver for OpenAPI specifications.

Provides resolveSchema tool for expanding $ref references in schemas.
"""

import logging
import copy
from typing import Any

logger = logging.getLogger("openapi-mcp.tools.schema_resolver")

# Maximum recursion depth to prevent infinite loops
MAX_DEPTH = 50


def resolve_schema(
    spec_store,
    schema_name: str,
    depth: int = 0,
    visited: set[str] | None = None,
) -> dict[str, Any]:
    """
    Resolve a schema by expanding all $ref references recursively.

    Args:
        spec_store: SpecStore instance
        schema_name: Schema name (e.g., "User" or "#/components/schemas/User")
        depth: Current recursion depth (for cycle detection)
        visited: Set of already-visited schema names (for cycle detection)

    Returns:
        Dict with schema definition, all $ref expanded recursively

    Raises:
        KeyError: If schema not found
        RuntimeError: If max depth exceeded
    """

    if not spec_store.is_loaded():
        raise KeyError("Spec not loaded")

    if visited is None:
        visited = set()

    # Handle $ref format
    if schema_name.startswith("#/components/schemas/"):
        schema_name = schema_name.replace("#/components/schemas/", "")

    logger.debug(f"Resolving schema: {schema_name} (depth={depth})")

    # Check max depth
    if depth > MAX_DEPTH:
        logger.warning(f"Max recursion depth exceeded for {schema_name}")
        raise RuntimeError(f"Max recursion depth exceeded for schema {schema_name}")

    # Check for cycles
    if schema_name in visited:
        logger.debug(f"Circular reference detected for {schema_name}")
        # Return a marker for circular reference instead of infinite loop
        return {"$ref": f"#/components/schemas/{schema_name}", "__circular__": True}

    visited.add(schema_name)

    # Get the schema
    try:
        schema = spec_store.get_schema(schema_name)
    except KeyError as e:
        logger.error(f"Schema not found: {schema_name}")
        raise KeyError(f"Schema not found: {schema_name}") from e

    # Deep copy to avoid modifying original
    resolved = copy.deepcopy(schema)

    # Recursively resolve all $ref in the schema
    _resolve_refs_recursive(resolved, spec_store, depth + 1, visited)

    visited.discard(schema_name)
    return resolved


def _resolve_refs_recursive(
    obj: Any,
    spec_store,
    depth: int,
    visited: set[str],
) -> None:
    """
    Recursively resolve $ref in an object.

    Modifies obj in place.
    """

    if depth > MAX_DEPTH:
        logger.warning("Max recursion depth exceeded during resolution")
        return

    if isinstance(obj, dict):
        # Check for $ref at this level
        if "$ref" in obj:
            ref = obj["$ref"]
            if ref.startswith("#/components/schemas/"):
                schema_name = ref.replace("#/components/schemas/", "")

                # Check for cycles before resolving
                if schema_name not in visited:
                    try:
                        resolved_schema = resolve_schema(
                            spec_store, schema_name, depth=depth, visited=visited.copy()
                        )
                        # Replace the entire object with resolved schema
                        obj.clear()
                        obj.update(resolved_schema)
                    except (KeyError, RuntimeError) as e:
                        logger.warning(f"Could not resolve $ref {ref}: {e}")
                        # Keep the $ref as is
                        pass
                else:
                    # Circular reference - mark it
                    obj["__circular__"] = True
                    logger.debug(f"Circular reference detected for {schema_name}")
        else:
            # Recursively process all values
            for _key, value in obj.items():
                _resolve_refs_recursive(value, spec_store, depth + 1, visited)

    elif isinstance(obj, list):
        # Recursively process all items
        for item in obj:
            _resolve_refs_recursive(item, spec_store, depth + 1, visited)
