"""
Unit tests for S3: In-memory store optimization

Tests verify:
1. Finding endpoints by path pattern
2. Getting specific endpoints
3. Accessing all schemas
4. Getting specific schemas
5. Caching for optimization
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from core.spec_store import SpecStore, get_store


class TestS3InMemoryStore(unittest.TestCase):
    """Test in-memory spec store optimization."""

    def setUp(self):
        """Set up test fixtures."""
        self.spec = {
            "openapi": "3.0.0",
            "info": {"title": "Test API", "version": "1.0.0"},
            "paths": {
                "/users": {
                    "get": {
                        "operationId": "listUsers",
                        "summary": "List all users",
                        "responses": {"200": {"description": "Success"}},
                    },
                    "post": {
                        "operationId": "createUser",
                        "summary": "Create a user",
                        "responses": {"201": {"description": "Created"}},
                    },
                },
                "/users/{id}": {
                    "get": {
                        "operationId": "getUser",
                        "summary": "Get user by ID",
                        "parameters": [{"name": "id", "in": "path"}],
                        "responses": {"200": {"description": "Success"}},
                    },
                    "put": {
                        "operationId": "updateUser",
                        "summary": "Update a user",
                        "responses": {"200": {"description": "Success"}},
                    },
                },
                "/posts": {
                    "get": {
                        "operationId": "listPosts",
                        "summary": "List all posts",
                        "responses": {"200": {"description": "Success"}},
                    }
                },
            },
            "components": {
                "schemas": {
                    "User": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "integer"},
                            "name": {"type": "string"},
                        },
                    },
                    "Post": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "integer"},
                            "title": {"type": "string"},
                            "userId": {"type": "integer"},
                        },
                    },
                }
            },
        }

        self.store = SpecStore()
        self.store.set_spec(self.spec)

    # AC 1: Find endpoints
    def test_find_endpoints_exact_path(self):
        """AC 1: Find endpoints with exact path."""
        endpoints = self.store.find_endpoints("/users")
        self.assertEqual(len(endpoints), 2)  # GET and POST

        methods = [ep["method"] for ep in endpoints]
        self.assertIn("GET", methods)
        self.assertIn("POST", methods)

    def test_find_endpoints_pattern(self):
        """AC 1: Find endpoints with pattern."""
        endpoints = self.store.find_endpoints("/users.*")
        self.assertEqual(
            len(endpoints), 4
        )  # /users (GET, POST) + /users/{id} (GET, PUT)

    def test_find_endpoints_not_found(self):
        """AC 1: Return empty list if no endpoints found."""
        endpoints = self.store.find_endpoints("/nonexistent")
        self.assertEqual(endpoints, [])

    def test_find_endpoints_with_operation_id(self):
        """AC 1: Include operation ID in results."""
        endpoints = self.store.find_endpoints("/users")
        for endpoint in endpoints:
            self.assertIn("operationId", endpoint)
            self.assertIsNotNone(endpoint["operationId"])

    # AC 2: Get specific endpoint
    def test_get_endpoint_success(self):
        """AC 2: Get endpoint by path and method."""
        endpoint = self.store.get_endpoint("/users", "GET")
        self.assertEqual(endpoint["summary"], "List all users")
        self.assertEqual(endpoint["operationId"], "listUsers")

    def test_get_endpoint_different_methods(self):
        """AC 2: Get different methods for same path."""
        get_endpoint = self.store.get_endpoint("/users", "GET")
        post_endpoint = self.store.get_endpoint("/users", "POST")

        self.assertNotEqual(get_endpoint, post_endpoint)
        self.assertEqual(get_endpoint["operationId"], "listUsers")
        self.assertEqual(post_endpoint["operationId"], "createUser")

    def test_get_endpoint_path_not_found(self):
        """AC 2: Raise KeyError if path not found."""
        with self.assertRaises(KeyError):
            self.store.get_endpoint("/nonexistent", "GET")

    def test_get_endpoint_method_not_found(self):
        """AC 2: Raise KeyError if method not found."""
        with self.assertRaises(KeyError):
            self.store.get_endpoint("/users", "DELETE")

    def test_get_endpoint_case_insensitive(self):
        """AC 2: Method comparison is case-insensitive."""
        endpoint = self.store.get_endpoint("/users", "get")  # lowercase
        self.assertEqual(endpoint["operationId"], "listUsers")

    # AC 3: Get all schemas
    def test_get_all_schemas_success(self):
        """AC 3: Get all schemas as dict."""
        schemas = self.store.get_all_schemas()
        self.assertIsInstance(schemas, dict)
        self.assertIn("User", schemas)
        self.assertIn("Post", schemas)

    def test_get_all_schemas_empty(self):
        """AC 3: Return empty dict if no schemas."""
        store = SpecStore()
        store.set_spec({"openapi": "3.0.0", "info": {}, "paths": {}})
        schemas = store.get_all_schemas()
        self.assertEqual(schemas, {})

    def test_get_all_schemas_not_loaded(self):
        """AC 3: Return empty dict if spec not loaded."""
        store = SpecStore()
        schemas = store.get_all_schemas()
        self.assertEqual(schemas, {})

    # AC 4: Get schema by name
    def test_get_schema_by_name(self):
        """AC 4: Get schema by simple name."""
        user_schema = self.store.get_schema("User")
        self.assertEqual(user_schema["type"], "object")
        self.assertIn("id", user_schema["properties"])

    def test_get_schema_by_ref(self):
        """AC 4: Get schema by $ref format."""
        user_schema = self.store.get_schema("#/components/schemas/User")
        self.assertEqual(user_schema["type"], "object")

    def test_get_schema_not_found(self):
        """AC 4: Raise KeyError if schema not found."""
        with self.assertRaises(KeyError):
            self.store.get_schema("NonexistentSchema")

    def test_get_schema_multiple(self):
        """AC 4: Get different schemas."""
        user_schema = self.store.get_schema("User")
        post_schema = self.store.get_schema("Post")

        self.assertNotEqual(user_schema, post_schema)
        self.assertIn("userId", post_schema["properties"])

    # AC 5: Caching
    def test_caching_schemas(self):
        """AC 5: Schema caching works."""
        # First call builds cache
        schemas1 = self.store.get_all_schemas()

        # Second call should use cache
        schemas2 = self.store.get_all_schemas()

        # Should be same object (cached)
        self.assertIs(schemas1, schemas2)

    def test_cache_cleared_on_set_spec(self):
        """AC 5: Cache is cleared when new spec is set."""
        schemas1 = self.store.get_all_schemas()

        # Set new spec
        new_spec = {
            "openapi": "3.0.0",
            "info": {},
            "paths": {},
            "components": {"schemas": {"NewSchema": {"type": "string"}}},
        }
        self.store.set_spec(new_spec)

        # Cache should be cleared and rebuilt
        schemas2 = self.store.get_all_schemas()
        self.assertNotEqual(schemas1, schemas2)
        self.assertIn("NewSchema", schemas2)

    def test_cache_cleared_on_clear(self):
        """AC 5: Cache is cleared on clear()."""
        schemas1 = self.store.get_all_schemas()
        self.assertIsNotNone(schemas1)

        self.store.clear()

        # After clear, should get empty dict
        schemas2 = self.store.get_all_schemas()
        self.assertEqual(schemas2, {})

    # Integration tests
    def test_find_and_get_endpoint_flow(self):
        """Integration: Find endpoints, then get details."""
        # Find all endpoints with /users in path
        endpoints = self.store.find_endpoints("/users.*")

        # Get details for each
        for endpoint_info in endpoints:
            path = endpoint_info["path"]
            method = endpoint_info["method"]

            endpoint = self.store.get_endpoint(path, method)
            self.assertIsNotNone(endpoint)
            self.assertIn("operationId", endpoint)

    def test_schema_reference_resolution(self):
        """Integration: Schema should be resolvable."""
        # Find endpoint that references schema
        endpoint = self.store.get_endpoint("/users", "POST")

        # Should be able to get related schemas
        user_schema = self.store.get_schema("User")
        self.assertIsNotNone(user_schema)

    def test_global_store_instance(self):
        """Integration: Global store instance works."""
        store = get_store()
        store.set_spec(self.spec)

        # Should find endpoints through global instance
        endpoints = store.find_endpoints("/users")
        self.assertGreater(len(endpoints), 0)


if __name__ == "__main__":
    unittest.main()
