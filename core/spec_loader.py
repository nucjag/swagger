"""
OpenAPI spec loader.

Responsible for:
- Fetching spec from URL
- Parsing JSON/YAML
- Validating OpenAPI 3.0+ structure
"""

import logging
import json
from pathlib import Path
from typing import Any

import requests

logger = logging.getLogger("openapi-mcp.spec_loader")

# Default cache path (will be set by openapi-mcp-server.py)
SPEC_CACHE_PATH = Path(".claude/mcp/swagger/openapi.local.json")


def load_spec_from_url(url: str, timeout: int = 15) -> dict:
    """
    Load OpenAPI spec from URL.

    Args:
        url: HTTP URL pointing to OpenAPI spec (JSON)
        timeout: Request timeout in seconds (default: 15)

    Returns:
        dict: Parsed OpenAPI specification

    Raises:
        ValueError: If URL is invalid or spec cannot be parsed
        requests.RequestException: If network request fails
    """
    if not url:
        raise ValueError("URL cannot be empty. Set OPENAPI_SPEC_URL in .env")

    logger.info(f"Loading spec from: {url}")

    try:
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()

        # Parse JSON
        spec = response.json()
        logger.info(f"Spec loaded successfully ({len(response.text)} bytes)")

        return spec

    except requests.exceptions.Timeout:
        raise ValueError(
            f"Timeout while loading spec from {url}. "
            f"Check that the URL is reachable and increase timeout if needed."
        )
    except requests.exceptions.ConnectionError as e:
        raise ValueError(
            f"Failed to connect to {url}. "
            f"Check that the URL is valid and reachable.\n"
            f"Error: {e!s}"
        )
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in spec from {url}. Error: {e!s}")
    except requests.exceptions.RequestException as e:
        raise ValueError(f"Error loading spec from {url}: {e!s}")


def validate_spec(spec: dict[str, Any]) -> bool:
    """
    Validate that spec is valid OpenAPI 3.0+.

    Args:
        spec: Parsed OpenAPI specification

    Returns:
        bool: True if spec is valid

    Raises:
        ValueError: If spec is invalid
    """
    if not isinstance(spec, dict):
        raise ValueError("Spec must be a dictionary")

    # Check required OpenAPI fields
    required_fields = ["openapi", "info", "paths"]
    missing_fields = [field for field in required_fields if field not in spec]

    if missing_fields:
        raise ValueError(
            f"Invalid OpenAPI spec: missing required fields: {', '.join(missing_fields)}"
        )

    # Validate openapi version
    openapi_version = spec.get("openapi", "")
    if not openapi_version.startswith("3."):
        raise ValueError(
            f"Unsupported OpenAPI version: {openapi_version}. "
            f"This server supports OpenAPI 3.0+ only."
        )

    # Validate paths
    if not isinstance(spec.get("paths"), dict):
        raise ValueError("'paths' must be a dictionary")

    # Validate info
    if not isinstance(spec.get("info"), dict):
        raise ValueError("'info' must be a dictionary")

    logger.info(
        f"Spec validated successfully (OpenAPI {openapi_version}, "
        f"{len(spec.get('paths', {}))} endpoints)"
    )

    return True


def save_spec_to_cache(spec: dict[str, Any], cache_path: Path | None = None) -> Path:
    """
    Save spec to local JSON file for caching.

    Args:
        spec: Parsed OpenAPI specification
        cache_path: Path to save spec (default: openapi.local.json)

    Returns:
        Path: Path where spec was saved
    """
    if cache_path is None:
        cache_path = SPEC_CACHE_PATH

    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)

        with cache_path.open("w") as f:
            json.dump(spec, f, indent=2)

        logger.info(f"Spec cached at {cache_path}")
        return cache_path

    except OSError as e:
        logger.warning(f"Failed to cache spec: {e!s}")
        raise


def load_spec_from_cache(cache_path: Path | None = None) -> dict[str, Any] | None:
    """
    Load spec from local cache file.

    Args:
        cache_path: Path to cached spec (default: openapi.local.json)

    Returns:
        dict: Parsed spec, or None if cache doesn't exist

    Raises:
        ValueError: If cache file is corrupted
    """
    if cache_path is None:
        cache_path = SPEC_CACHE_PATH

    if not cache_path.exists():
        logger.warning(f"Cache file not found: {cache_path}")
        return None

    try:
        with cache_path.open() as f:
            spec = json.load(f)

        logger.info(f"Spec loaded from cache: {cache_path}")
        return spec

    except json.JSONDecodeError as e:
        raise ValueError(f"Corrupted cache file {cache_path}: {e!s}")
    except OSError as e:
        logger.warning(f"Failed to read cache: {e!s}")
        return None
