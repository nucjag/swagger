"""
Common utilities for OpenAPI MCP Server.

Provides:
- Error handling and custom exceptions
- Type conversion helpers
- Logging utilities
"""

import logging
from typing import Any

logger = logging.getLogger("openapi-mcp.utils")


class SpecError(Exception):
    """Base exception for spec-related errors."""

    pass


class EndpointNotFoundError(SpecError):
    """Raised when endpoint is not found in spec."""

    pass


class SchemaNotFoundError(SpecError):
    """Raised when schema is not found in spec."""

    pass


class ValidationError(SpecError):
    """Raised when validation fails."""

    pass


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """
    Deep merge two dictionaries.

    Args:
        base: Base dictionary
        override: Dictionary with overrides

    Returns:
        dict: Merged dictionary
    """
    # TODO: Implementation in S2-S3 as needed
    pass


def resolve_ref(ref: str, spec: dict[str, Any]) -> dict[str, Any]:
    """
    Resolve a JSON reference ($ref) in a spec.

    Args:
        ref: Reference string (e.g. "#/components/schemas/User")
        spec: OpenAPI specification

    Returns:
        dict: Resolved schema

    Raises:
        SchemaNotFoundError: If reference cannot be resolved
    """
    # TODO: S6 (resolveSchema) implementation
    pass
