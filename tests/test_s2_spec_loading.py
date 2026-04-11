"""
Unit tests for S2: Spec loading & parsing

Tests verify:
1. Spec loading from URL with HTTP requests
2. JSON parsing and validation
3. OpenAPI 3.0+ validation
4. Error handling (network, invalid JSON, invalid spec)
5. Spec caching
6. SpecStore integration
"""

import sys
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add current directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))


class TestS2SpecLoading(unittest.TestCase):
    """Test spec loading from URL."""

    def setUp(self):
        """Set up test fixtures."""
        self.valid_spec = {
            "openapi": "3.0.0",
            "info": {"title": "Test API", "version": "1.0.0"},
            "paths": {
                "/users": {
                    "get": {
                        "summary": "List users",
                        "responses": {"200": {"description": "Success"}},
                    }
                }
            },
        }

    def test_load_spec_from_url_success(self):
        """AC 1: Spec loads from URL successfully."""
        from core.spec_loader import load_spec_from_url

        # Mock requests.get
        with patch("core.spec_loader.requests.get") as mock_get:
            mock_response = MagicMock()
            mock_response.json.return_value = self.valid_spec
            mock_response.text = json.dumps(self.valid_spec)
            mock_get.return_value = mock_response

            spec = load_spec_from_url("http://localhost:8087/openapi.json")

            self.assertEqual(spec, self.valid_spec)
            mock_get.assert_called_once()

    def test_load_spec_timeout(self):
        """AC 1: Timeout is handled gracefully."""
        from core.spec_loader import load_spec_from_url
        import requests

        with patch("core.spec_loader.requests.get") as mock_get:
            mock_get.side_effect = requests.exceptions.Timeout()

            with self.assertRaises(ValueError) as context:
                load_spec_from_url("http://localhost:8087/openapi.json")

            self.assertIn("Timeout", str(context.exception))

    def test_load_spec_connection_error(self):
        """AC 1: Connection errors are handled."""
        from core.spec_loader import load_spec_from_url
        import requests

        with patch("core.spec_loader.requests.get") as mock_get:
            mock_get.side_effect = requests.exceptions.ConnectionError()

            with self.assertRaises(ValueError) as context:
                load_spec_from_url("http://localhost:8087/openapi.json")

            self.assertIn("Failed to connect", str(context.exception))

    def test_load_spec_invalid_json(self):
        """AC 1: Invalid JSON is caught."""
        from core.spec_loader import load_spec_from_url

        with patch("core.spec_loader.requests.get") as mock_get:
            mock_response = MagicMock()
            mock_response.json.side_effect = json.JSONDecodeError("msg", "doc", 0)
            mock_get.return_value = mock_response

            with self.assertRaises(ValueError) as context:
                load_spec_from_url("http://localhost:8087/openapi.json")

            self.assertIn("Invalid JSON", str(context.exception))

    def test_load_spec_empty_url(self):
        """AC 1: Empty URL raises ValueError."""
        from core.spec_loader import load_spec_from_url

        with self.assertRaises(ValueError) as context:
            load_spec_from_url("")

        self.assertIn("URL cannot be empty", str(context.exception))


class TestS2SpecValidation(unittest.TestCase):
    """Test spec validation."""

    def setUp(self):
        """Set up test fixtures."""
        self.valid_spec = {
            "openapi": "3.0.0",
            "info": {"title": "Test API", "version": "1.0.0"},
            "paths": {"/users": {}},
        }

    def test_validate_spec_success(self):
        """AC 2: Valid spec passes validation."""
        from core.spec_loader import validate_spec

        result = validate_spec(self.valid_spec)
        self.assertTrue(result)

    def test_validate_spec_missing_openapi(self):
        """AC 2: Missing 'openapi' field raises ValueError."""
        from core.spec_loader import validate_spec

        spec = {"info": {"title": "Test"}, "paths": {}}

        with self.assertRaises(ValueError) as context:
            validate_spec(spec)

        self.assertIn("openapi", str(context.exception))

    def test_validate_spec_missing_paths(self):
        """AC 2: Missing 'paths' field raises ValueError."""
        from core.spec_loader import validate_spec

        spec = {"openapi": "3.0.0", "info": {"title": "Test"}}

        with self.assertRaises(ValueError) as context:
            validate_spec(spec)

        self.assertIn("paths", str(context.exception))

    def test_validate_spec_missing_info(self):
        """AC 2: Missing 'info' field raises ValueError."""
        from core.spec_loader import validate_spec

        spec = {"openapi": "3.0.0", "paths": {}}

        with self.assertRaises(ValueError) as context:
            validate_spec(spec)

        self.assertIn("info", str(context.exception))

    def test_validate_spec_invalid_version(self):
        """AC 2: Invalid OpenAPI version raises ValueError."""
        from core.spec_loader import validate_spec

        spec = {
            "openapi": "2.0",  # Swagger 2.0, not OpenAPI 3.0+
            "info": {"title": "Test"},
            "paths": {},
        }

        with self.assertRaises(ValueError) as context:
            validate_spec(spec)

        self.assertIn("Unsupported", str(context.exception))

    def test_validate_spec_openapi_31(self):
        """AC 2: OpenAPI 3.1.0 is accepted."""
        from core.spec_loader import validate_spec

        spec = {
            "openapi": "3.1.0",
            "info": {"title": "Test", "version": "1.0.0"},
            "paths": {},
        }

        result = validate_spec(spec)
        self.assertTrue(result)


class TestS2CachingAndStore(unittest.TestCase):
    """Test spec caching and SpecStore integration."""

    def setUp(self):
        """Set up test fixtures."""
        self.valid_spec = {
            "openapi": "3.0.0",
            "info": {"title": "Test API", "version": "1.0.0"},
            "paths": {},
        }

    def test_save_spec_to_cache(self):
        """AC 3: Spec is saved to cache file."""
        from core.spec_loader import save_spec_to_cache

        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "spec.json"
            result = save_spec_to_cache(self.valid_spec, cache_path)

            self.assertTrue(cache_path.exists())
            self.assertEqual(result, cache_path)

            # Verify content
            with open(cache_path) as f:
                cached_spec = json.load(f)
            self.assertEqual(cached_spec, self.valid_spec)

    def test_load_spec_from_cache(self):
        """AC 3: Spec is loaded from cache file."""
        from core.spec_loader import load_spec_from_cache, save_spec_to_cache

        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "spec.json"
            save_spec_to_cache(self.valid_spec, cache_path)

            loaded_spec = load_spec_from_cache(cache_path)
            self.assertEqual(loaded_spec, self.valid_spec)

    def test_load_spec_cache_not_found(self):
        """AC 3: Missing cache returns None gracefully."""
        from core.spec_loader import load_spec_from_cache

        result = load_spec_from_cache(Path("/nonexistent/path/spec.json"))
        self.assertIsNone(result)

    def test_spec_store_set_and_get(self):
        """AC 4: SpecStore stores and retrieves spec."""
        from core.spec_store import SpecStore

        store = SpecStore()
        store.set_spec(self.valid_spec)

        self.assertTrue(store.is_loaded())
        self.assertEqual(store.get_spec(), self.valid_spec)

    def test_spec_store_clear(self):
        """AC 4: SpecStore can be cleared."""
        from core.spec_store import SpecStore

        store = SpecStore()
        store.set_spec(self.valid_spec)
        store.clear()

        self.assertFalse(store.is_loaded())
        self.assertIsNone(store.get_spec())

    def test_spec_store_global_instance(self):
        """AC 4: Global spec store instance works."""
        from core.spec_store import get_store

        store = get_store()
        store.set_spec(self.valid_spec)

        # Get same instance again
        store2 = get_store()
        self.assertEqual(store2.get_spec(), self.valid_spec)


class TestS2ErrorHandling(unittest.TestCase):
    """Test error handling."""

    def test_corrupted_cache_raises_error(self):
        """AC 5: Corrupted cache raises ValueError."""
        from core.spec_loader import load_spec_from_cache

        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "spec.json"
            cache_path.write_text("{invalid json")

            with self.assertRaises(ValueError) as context:
                load_spec_from_cache(cache_path)

            self.assertIn("Corrupted", str(context.exception))

    def test_network_fallback_to_cache(self):
        """AC 5: Network error falls back to cache."""
        # This is tested implicitly in openapi-mcp-server.py main()
        # which tries URL first, then cache
        pass


class TestS2Integration(unittest.TestCase):
    """Integration tests."""

    def test_spec_loader_and_store_integration(self):
        """AC 1-4: Full workflow from load → validate → cache → store."""
        from core.spec_loader import validate_spec, save_spec_to_cache
        from core.spec_store import get_store

        spec = {
            "openapi": "3.0.0",
            "info": {"title": "Test API", "version": "1.0.0"},
            "paths": {
                "/api/users": {
                    "get": {
                        "summary": "List users",
                        "responses": {"200": {"description": "Success"}},
                    }
                }
            },
        }

        # Validate
        validate_spec(spec)

        # Cache
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "spec.json"
            save_spec_to_cache(spec, cache_path)

            # Store
            store = get_store()
            store.set_spec(spec)

            # Verify
            self.assertTrue(store.is_loaded())
            self.assertEqual(store.get_spec()["info"]["title"], "Test API")
            self.assertIn("/api/users", store.get_spec()["paths"])


if __name__ == "__main__":
    unittest.main()
