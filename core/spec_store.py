"""
In-memory storage for OpenAPI specifications.

Provides:
- Thread-safe access to cached spec
- Lazy loading with caching
- Methods for spec retrieval and updates
- Optimized access to endpoints and schemas
"""

import logging
import re
from typing import Optional, Dict, Any, List

logger = logging.getLogger("openapi-mcp.spec_store")


class SpecStore:
    """In-memory store for OpenAPI specifications."""

    def __init__(self):
        self._spec: Optional[Dict[str, Any]] = None
        self._loaded = False

        # Caches for optimization
        self._endpoints_cache: Optional[Dict[str, List[Dict[str, Any]]]] = None
        self._schemas_cache: Optional[Dict[str, Any]] = None

    def set_spec(self, spec: Dict[str, Any]) -> None:
        """
        Set the current OpenAPI spec and clear caches.

        Args:
            spec: Parsed OpenAPI specification
        """
        self._spec = spec
        self._loaded = True
        self._clear_caches()
        logger.info(f"Spec loaded: {len(spec)} keys")

    def get_spec(self) -> Optional[Dict[str, Any]]:
        """Get the current OpenAPI spec."""
        return self._spec

    def is_loaded(self) -> bool:
        """Check if spec is loaded."""
        return self._loaded

    def clear(self) -> None:
        """Clear the cached spec and all caches."""
        self._spec = None
        self._loaded = False
        self._clear_caches()

    def _clear_caches(self) -> None:
        """Clear internal caches."""
        self._endpoints_cache = None
        self._schemas_cache = None

    def find_endpoints(self, path_pattern: str) -> List[Dict[str, Any]]:
        """
        Find endpoints matching a path pattern.

        Args:
            path_pattern: Path pattern (exact or regex, e.g., "/users" or "/users/.*")

        Returns:
            List of endpoint objects with path and methods
        """
        if not self._loaded or not self._spec:
            logger.warning("Spec not loaded")
            return []

        logger.debug(f"Finding endpoints matching pattern: {path_pattern}")

        paths = self._spec.get("paths", {})
        results = []

        try:
            # Try regex match first
            pattern_re = re.compile(f"^{path_pattern}$")
            is_regex = True
        except re.error:
            # Fallback to exact match
            is_regex = False

        for path, path_item in paths.items():
            if is_regex:
                if not pattern_re.match(path):
                    continue
            else:
                if path != path_pattern:
                    continue

            # Add this path with all its methods
            for method, operation in path_item.items():
                if method.lower() in [
                    "get",
                    "post",
                    "put",
                    "delete",
                    "patch",
                    "head",
                    "options",
                ]:
                    results.append(
                        {
                            "path": path,
                            "method": method.upper(),
                            "operationId": operation.get(
                                "operationId", f"{method.upper()} {path}"
                            ),
                            "summary": operation.get("summary", ""),
                            "operation": operation,
                        }
                    )

        logger.debug(f"Found {len(results)} endpoints matching pattern")
        return results

    def get_endpoint(self, path: str, method: str) -> Dict[str, Any]:
        """
        Get a specific endpoint operation.

        Args:
            path: API path (e.g., "/users/{id}")
            method: HTTP method (GET, POST, etc.)

        Returns:
            Endpoint operation object

        Raises:
            KeyError: If endpoint not found
        """
        if not self._loaded or not self._spec:
            raise KeyError("Spec not loaded")

        method_lower = method.lower()
        logger.debug(f"Getting endpoint: {method_lower.upper()} {path}")

        paths = self._spec.get("paths", {})
        if path not in paths:
            raise KeyError(f"Path not found: {path}")

        if method_lower not in paths[path]:
            raise KeyError(f"Method {method_lower.upper()} not found for path {path}")

        return paths[path][method_lower]

    def get_all_schemas(self) -> Dict[str, Any]:
        """
        Get all schemas from components.schemas.

        Returns:
            Dictionary of all schemas
        """
        if not self._loaded or not self._spec:
            return {}

        if self._schemas_cache is not None:
            logger.debug("Returning schemas from cache")
            return self._schemas_cache

        logger.debug("Building schemas cache")
        schemas = self._spec.get("components", {}).get("schemas", {})
        self._schemas_cache = schemas
        return schemas

    def get_schema(self, schema_name: str) -> Dict[str, Any]:
        """
        Get a specific schema by name.

        Args:
            schema_name: Schema name or $ref (e.g., "User" or "#/components/schemas/User")

        Returns:
            Schema object

        Raises:
            KeyError: If schema not found
        """
        if not self._loaded or not self._spec:
            raise KeyError("Spec not loaded")

        # Handle $ref format
        if schema_name.startswith("#/components/schemas/"):
            schema_name = schema_name.replace("#/components/schemas/", "")

        logger.debug(f"Getting schema: {schema_name}")

        all_schemas = self.get_all_schemas()
        if schema_name not in all_schemas:
            raise KeyError(f"Schema not found: {schema_name}")

        return all_schemas[schema_name]


# Global spec store instance
_store = SpecStore()


def get_store() -> SpecStore:
    """Get the global spec store instance."""
    return _store
