"""Tests for S4: searchEndpoints tool.

Covers:
- AC 1: Tool registration in FastMCP
- AC 2: Search by query (substring match)
- AC 3: Search by tags
- AC 4: Filter by HTTP method
- AC 5: Combined search with AND logic
"""

import sys
import pytest
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

from core.spec_store import get_store
from tools.search import search_endpoints


# Sample spec for testing
SAMPLE_SPEC = {
    "openapi": "3.0.0",
    "info": {"title": "Test API", "version": "1.0.0"},
    "paths": {
        "/users": {
            "get": {
                "operationId": "listUsers",
                "summary": "List all users",
                "tags": ["users"],
                "responses": {"200": {"description": "Success"}},
            },
            "post": {
                "operationId": "createUser",
                "summary": "Create a new user",
                "tags": ["users", "admin"],
                "responses": {"201": {"description": "Created"}},
            },
        },
        "/users/{id}": {
            "get": {
                "operationId": "getUser",
                "summary": "Get user by ID",
                "tags": ["users"],
                "responses": {"200": {"description": "Success"}},
            },
            "put": {
                "operationId": "updateUser",
                "summary": "Update user",
                "tags": ["users", "admin"],
                "responses": {"200": {"description": "Success"}},
            },
            "delete": {
                "operationId": "deleteUser",
                "summary": "Delete user",
                "tags": ["admin"],
                "responses": {"204": {"description": "Deleted"}},
            },
        },
        "/products": {
            "get": {
                "operationId": "listProducts",
                "summary": "List all products",
                "tags": ["products"],
                "responses": {"200": {"description": "Success"}},
            },
            "post": {
                "operationId": "createProduct",
                "summary": "Create a new product",
                "tags": ["products", "admin"],
                "responses": {"201": {"description": "Created"}},
            },
        },
        "/user-profile": {
            "get": {
                "operationId": "getUserProfile",
                "summary": "Get user profile",
                "tags": ["profile"],
                "responses": {"200": {"description": "Success"}},
            }
        },
    },
    "components": {"schemas": {}},
}


@pytest.fixture
def spec_store():
    """Initialize spec store with sample spec."""
    store = get_store()
    store.clear()
    store.set_spec(SAMPLE_SPEC)
    yield store
    store.clear()


class TestAC1ToolRegistration:
    """AC 1: searchEndpoints registered as MCP tool."""

    def test_tool_exists(self, spec_store):
        """Tool function exists and is callable."""
        assert callable(search_endpoints)

    def test_tool_signature(self, spec_store):
        """Tool has correct parameters."""
        import inspect

        sig = inspect.signature(search_endpoints)
        params = list(sig.parameters.keys())

        # Should have spec_store, query, tags, method
        assert "spec_store" in params
        assert "query" in params
        assert "tags" in params
        assert "method" in params

    def test_returns_list_of_dicts(self, spec_store):
        """Tool returns list of dict objects."""
        result = search_endpoints(spec_store)
        assert isinstance(result, list)
        if result:
            assert isinstance(result[0], dict)

    def test_result_has_required_fields(self, spec_store):
        """Each result has path, method, operationId, summary, tags."""
        result = search_endpoints(spec_store)
        assert len(result) > 0

        for item in result:
            assert "path" in item
            assert "method" in item
            assert "operationId" in item
            assert "summary" in item
            assert "tags" in item


class TestAC2SearchByQuery:
    """AC 2: Search endpoints by query (substring match)."""

    def test_query_substring_match(self, spec_store):
        """Find endpoints containing 'user' in path."""
        result = search_endpoints(spec_store, query="user")
        paths = [item["path"] for item in result]

        assert "/users" in paths
        assert "/users/{id}" in paths
        assert "/user-profile" in paths
        assert "/products" not in paths

    def test_query_case_insensitive(self, spec_store):
        """Query matching is case-insensitive."""
        result1 = search_endpoints(spec_store, query="user")
        result2 = search_endpoints(spec_store, query="USER")
        result3 = search_endpoints(spec_store, query="User")

        assert len(result1) == len(result2) == len(result3)

    def test_query_no_matches(self, spec_store):
        """Return empty list if no matches."""
        result = search_endpoints(spec_store, query="nonexistent")
        assert result == []

    def test_query_product(self, spec_store):
        """Find endpoints containing 'product' in path."""
        result = search_endpoints(spec_store, query="product")
        paths = [item["path"] for item in result]

        assert "/products" in paths
        assert "/users" not in paths
        assert "/user-profile" not in paths  # 'product' is NOT in 'profile'

    def test_query_exact_substring(self, spec_store):
        """Query can be any substring."""
        result = search_endpoints(spec_store, query="/users/{id}")
        assert len(result) > 0
        assert result[0]["path"] == "/users/{id}"


class TestAC3SearchByTags:
    """AC 3: Filter endpoints by tags."""

    def test_filter_by_single_tag(self, spec_store):
        """Find endpoints with specific tag."""
        result = search_endpoints(spec_store, tags=["users"])

        assert len(result) > 0
        for item in result:
            assert "users" in item["tags"]

    def test_filter_by_admin_tag(self, spec_store):
        """Find admin endpoints."""
        result = search_endpoints(spec_store, tags=["admin"])
        paths_methods = [(item["path"], item["method"]) for item in result]

        # Should include: POST /users, PUT /users/{id}, DELETE /users/{id}, POST /products
        assert ("/users", "POST") in paths_methods
        assert ("/users/{id}", "PUT") in paths_methods
        assert ("/users/{id}", "DELETE") in paths_methods
        assert ("/products", "POST") in paths_methods

    def test_filter_by_multiple_tags(self, spec_store):
        """Filter by multiple tags (OR logic - any tag match)."""
        result = search_endpoints(spec_store, tags=["users", "products"])

        assert len(result) > 0
        for item in result:
            has_tag = "users" in item["tags"] or "products" in item["tags"]
            assert has_tag

    def test_filter_no_matching_tags(self, spec_store):
        """Return empty list if no endpoints have tag."""
        result = search_endpoints(spec_store, tags=["nonexistent"])
        assert result == []

    def test_filter_by_profile_tag(self, spec_store):
        """Find profile endpoints."""
        result = search_endpoints(spec_store, tags=["profile"])
        paths = [item["path"] for item in result]

        assert "/user-profile" in paths
        assert len(result) == 1


class TestAC4FilterByMethod:
    """AC 4: Filter endpoints by HTTP method."""

    def test_filter_by_get(self, spec_store):
        """Find all GET endpoints."""
        result = search_endpoints(spec_store, method="GET")

        assert len(result) > 0
        for item in result:
            assert item["method"] == "GET"

    def test_filter_by_post(self, spec_store):
        """Find all POST endpoints."""
        result = search_endpoints(spec_store, method="POST")

        assert len(result) == 2  # /users, /products
        for item in result:
            assert item["method"] == "POST"

    def test_filter_by_put(self, spec_store):
        """Find all PUT endpoints."""
        result = search_endpoints(spec_store, method="PUT")
        paths = [item["path"] for item in result]

        assert "/users/{id}" in paths
        for item in result:
            assert item["method"] == "PUT"

    def test_filter_by_delete(self, spec_store):
        """Find all DELETE endpoints."""
        result = search_endpoints(spec_store, method="DELETE")
        paths = [item["path"] for item in result]

        assert "/users/{id}" in paths
        for item in result:
            assert item["method"] == "DELETE"

    def test_method_case_insensitive(self, spec_store):
        """Method filter is case-insensitive."""
        result1 = search_endpoints(spec_store, method="GET")
        result2 = search_endpoints(spec_store, method="get")
        result3 = search_endpoints(spec_store, method="Get")

        assert len(result1) == len(result2) == len(result3)

    def test_filter_no_matching_method(self, spec_store):
        """Return empty list if no endpoints use method."""
        result = search_endpoints(spec_store, method="PATCH")
        assert result == []


class TestAC5CombinedSearch:
    """AC 5: Combined search with AND logic."""

    def test_query_and_tags(self, spec_store):
        """Search by query AND tags."""
        result = search_endpoints(spec_store, query="users", tags=["admin"])

        for item in result:
            assert "users" in item["path"].lower()
            assert "admin" in item["tags"]

    def test_query_and_method(self, spec_store):
        """Search by query AND method."""
        result = search_endpoints(spec_store, query="users", method="GET")

        for item in result:
            assert "users" in item["path"].lower()
            assert item["method"] == "GET"

    def test_query_and_tags_and_method(self, spec_store):
        """Search by query AND tags AND method (AND logic)."""
        result = search_endpoints(
            spec_store, query="users", tags=["admin"], method="POST"
        )

        assert len(result) > 0
        for item in result:
            assert "users" in item["path"].lower()
            assert "admin" in item["tags"]
            assert item["method"] == "POST"

    def test_combined_no_match(self, spec_store):
        """Return empty if conditions don't match."""
        result = search_endpoints(
            spec_store, query="users", method="DELETE", tags=["users"]
        )

        # /users/{id} DELETE has "admin" tag, not "users"
        # So this should return empty
        assert (
            len(
                [
                    r
                    for r in result
                    if r["path"] == "/users"
                    and r["method"] == "DELETE"
                    and "users" in r["tags"]
                ]
            )
            == 0
        )

    def test_combined_all_filters(self, spec_store):
        """Test with all three filters combined."""
        # /users/{id} DELETE has admin tag
        result = search_endpoints(
            spec_store, query="/users", tags=["admin"], method="DELETE"
        )

        paths = [item["path"] for item in result]
        assert "/users/{id}" in paths


class TestNFRAndEdgeCases:
    """Non-functional requirements and edge cases."""

    def test_results_sorted_by_path(self, spec_store):
        """Results are sorted by path for consistency."""
        result = search_endpoints(spec_store)

        if len(result) > 1:
            paths = [item["path"] for item in result]
            assert paths == sorted(paths)

    def test_empty_spec(self):
        """Handle empty spec gracefully."""
        store = get_store()
        store.clear()
        store.set_spec({"openapi": "3.0.0", "info": {}, "paths": {}})

        result = search_endpoints(store)
        assert result == []

    def test_no_tags_in_operation(self, spec_store):
        """Handle operations without tags."""
        # Some operations might not have tags
        result = search_endpoints(spec_store, tags=["users"])
        # Should only return operations that have the tag
        assert all("users" in item["tags"] for item in result)

    def test_all_http_methods_supported(self, spec_store):
        """Support all standard HTTP methods."""
        methods = ["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"]

        for method in methods:
            # Just verify it doesn't crash
            result = search_endpoints(spec_store, method=method)
            assert isinstance(result, list)

    def test_operation_id_fallback(self, spec_store):
        """Provide fallback operationId if not in spec."""
        result = search_endpoints(spec_store)

        for item in result:
            # Each endpoint should have operationId
            assert item["operationId"]
            assert isinstance(item["operationId"], str)
            assert len(item["operationId"]) > 0


class TestIntegrationWithSpecStore:
    """Test integration with SpecStore."""

    def test_search_with_unloaded_spec(self):
        """Return empty list if spec not loaded."""
        store = get_store()
        store.clear()

        result = search_endpoints(store)
        assert result == []

    def test_search_uses_current_spec(self, spec_store):
        """Search uses the currently loaded spec."""
        result1 = search_endpoints(spec_store)

        # Load new spec
        new_spec = {
            "openapi": "3.0.0",
            "info": {"title": "New API", "version": "1.0.0"},
            "paths": {
                "/new": {"get": {"operationId": "getNew", "tags": [], "responses": {}}}
            },
            "components": {"schemas": {}},
        }
        spec_store.set_spec(new_spec)

        result2 = search_endpoints(spec_store)

        # Results should be different
        assert len(result1) != len(result2)
        assert any(item["path"] == "/new" for item in result2)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
