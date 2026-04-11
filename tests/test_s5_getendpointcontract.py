"""Tests for S5: getEndpointContract tool.

Covers:
- AC 1: Tool registration in FastMCP
- AC 2: Full contract structure
- AC 3: Parameters (query, path, header, cookie)
- AC 4: RequestBody with content types
- AC 5: Responses with examples and headers
"""

import sys
import pytest
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

from core.spec_store import get_store
from tools.contract import get_endpoint_contract


# Sample spec with full contract details
SAMPLE_SPEC = {
    "openapi": "3.0.0",
    "info": {"title": "Test API", "version": "1.0.0"},
    "paths": {
        "/users": {
            "get": {
                "operationId": "listUsers",
                "summary": "List all users",
                "description": "Returns a paginated list of users",
                "tags": ["users"],
                "parameters": [
                    {
                        "name": "limit",
                        "in": "query",
                        "required": False,
                        "schema": {"type": "integer"},
                        "description": "Max number of users",
                        "example": 10,
                    },
                    {
                        "name": "offset",
                        "in": "query",
                        "required": False,
                        "schema": {"type": "integer"},
                        "description": "Pagination offset",
                        "example": 0,
                    },
                ],
                "responses": {
                    "200": {
                        "description": "Success",
                        "content": {
                            "application/json": {
                                "schema": {"type": "object"},
                                "example": {"users": [], "total": 0},
                            }
                        },
                        "headers": {
                            "X-Total-Count": {
                                "description": "Total count of users",
                                "schema": {"type": "integer"},
                            }
                        },
                    },
                    "401": {"description": "Unauthorized"},
                },
            },
            "post": {
                "operationId": "createUser",
                "summary": "Create a new user",
                "description": "Creates a new user with provided data",
                "tags": ["users", "admin"],
                "requestBody": {
                    "required": True,
                    "description": "User data",
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string"},
                                    "email": {"type": "string"},
                                },
                            },
                            "example": {"name": "John", "email": "john@example.com"},
                        }
                    },
                },
                "responses": {
                    "201": {
                        "description": "Created",
                        "content": {"application/json": {"schema": {"type": "object"}}},
                    },
                    "400": {"description": "Bad Request"},
                },
                "security": [{"bearerAuth": []}],
            },
        },
        "/users/{id}": {
            "get": {
                "operationId": "getUser",
                "summary": "Get user by ID",
                "tags": ["users"],
                "parameters": [
                    {
                        "name": "id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string"},
                        "description": "User ID",
                    },
                    {
                        "name": "X-Auth-Token",
                        "in": "header",
                        "required": False,
                        "schema": {"type": "string"},
                        "description": "Auth token",
                    },
                ],
                "responses": {
                    "200": {
                        "description": "Success",
                        "content": {"application/json": {"schema": {"type": "object"}}},
                    },
                    "404": {"description": "Not Found"},
                },
            },
            "put": {
                "operationId": "updateUser",
                "summary": "Update user",
                "deprecated": True,
                "tags": ["users", "admin"],
                "parameters": [
                    {
                        "name": "id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string"},
                    }
                ],
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {"schema": {"type": "object"}},
                        "application/x-www-form-urlencoded": {
                            "schema": {"type": "object"}
                        },
                    },
                },
                "responses": {"200": {"description": "Success"}},
            },
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
    """AC 1: getEndpointContract registered as MCP tool."""

    def test_tool_exists(self, spec_store):
        """Tool function exists and is callable."""
        assert callable(get_endpoint_contract)

    def test_tool_signature(self, spec_store):
        """Tool has correct parameters."""
        import inspect

        sig = inspect.signature(get_endpoint_contract)
        params = list(sig.parameters.keys())

        assert "spec_store" in params
        assert "path" in params
        assert "method" in params

    def test_returns_dict(self, spec_store):
        """Tool returns dict object."""
        result = get_endpoint_contract(spec_store, path="/users", method="GET")
        assert isinstance(result, dict)

    def test_result_has_required_fields(self, spec_store):
        """Contract has required fields."""
        result = get_endpoint_contract(spec_store, path="/users", method="GET")

        required_fields = ["path", "method", "operationId", "parameters", "responses"]
        for field in required_fields:
            assert field in result


class TestAC2ContractStructure:
    """AC 2: Full contract structure with all fields."""

    def test_path_and_method(self, spec_store):
        """Path and method are correct."""
        result = get_endpoint_contract(spec_store, path="/users/{id}", method="GET")

        assert result["path"] == "/users/{id}"
        assert result["method"] == "GET"

    def test_operation_id(self, spec_store):
        """operationId from spec."""
        result = get_endpoint_contract(spec_store, path="/users/{id}", method="GET")
        assert result["operationId"] == "getUser"

    def test_summary_and_description(self, spec_store):
        """Summary and description included."""
        result = get_endpoint_contract(spec_store, path="/users", method="GET")

        assert result["summary"] == "List all users"
        assert result["description"] == "Returns a paginated list of users"

    def test_tags_field(self, spec_store):
        """Tags field included."""
        result = get_endpoint_contract(spec_store, path="/users", method="POST")
        assert "tags" in result
        assert "users" in result["tags"]
        assert "admin" in result["tags"]

    def test_deprecated_field(self, spec_store):
        """Deprecated flag included."""
        result_not_deprecated = get_endpoint_contract(
            spec_store, path="/users", method="GET"
        )
        assert result_not_deprecated["deprecated"] is False

        result_deprecated = get_endpoint_contract(
            spec_store, path="/users/{id}", method="PUT"
        )
        assert result_deprecated["deprecated"] is True

    def test_security_field(self, spec_store):
        """Security field included when present."""
        result = get_endpoint_contract(spec_store, path="/users", method="POST")
        assert "security" in result
        assert result["security"] == [{"bearerAuth": []}]


class TestAC3Parameters:
    """AC 3: Parameters (query, path, header, cookie)."""

    def test_query_parameters(self, spec_store):
        """Query parameters included."""
        result = get_endpoint_contract(spec_store, path="/users", method="GET")

        assert len(result["parameters"]) == 2
        query_params = [p for p in result["parameters"] if p["in"] == "query"]
        assert len(query_params) == 2

        # Check parameter fields
        param = query_params[0]
        assert "name" in param
        assert "in" in param
        assert "schema" in param
        assert "required" in param
        assert "description" in param

    def test_path_parameters(self, spec_store):
        """Path parameters included."""
        result = get_endpoint_contract(spec_store, path="/users/{id}", method="GET")

        path_params = [p for p in result["parameters"] if p["in"] == "path"]
        assert len(path_params) == 1
        assert path_params[0]["name"] == "id"
        assert path_params[0]["required"] is True

    def test_header_parameters(self, spec_store):
        """Header parameters included."""
        result = get_endpoint_contract(spec_store, path="/users/{id}", method="GET")

        header_params = [p for p in result["parameters"] if p["in"] == "header"]
        assert len(header_params) == 1
        assert header_params[0]["name"] == "X-Auth-Token"

    def test_parameter_with_example(self, spec_store):
        """Parameter examples preserved."""
        result = get_endpoint_contract(spec_store, path="/users", method="GET")

        limit_param = [p for p in result["parameters"] if p["name"] == "limit"][0]
        assert limit_param.get("example") == 10


class TestAC4RequestBody:
    """AC 4: RequestBody with all content types."""

    def test_request_body_exists(self, spec_store):
        """RequestBody included for POST."""
        result = get_endpoint_contract(spec_store, path="/users", method="POST")

        assert "requestBody" in result
        assert result["requestBody"]["required"] is True

    def test_request_body_content_types(self, spec_store):
        """All content types included."""
        result = get_endpoint_contract(spec_store, path="/users/{id}", method="PUT")

        content = result["requestBody"]["content"]
        assert "application/json" in content
        assert "application/x-www-form-urlencoded" in content

    def test_request_body_schema(self, spec_store):
        """Schema and example included."""
        result = get_endpoint_contract(spec_store, path="/users", method="POST")

        json_content = result["requestBody"]["content"]["application/json"]
        assert "schema" in json_content
        assert "example" in json_content

    def test_no_request_body_for_get(self, spec_store):
        """GET request has no requestBody."""
        result = get_endpoint_contract(spec_store, path="/users", method="GET")

        # requestBody should not be present for GET
        assert "requestBody" not in result


class TestAC5Responses:
    """AC 5: Responses with examples and headers."""

    def test_responses_all_codes(self, spec_store):
        """All status codes included."""
        result = get_endpoint_contract(spec_store, path="/users", method="GET")

        responses = result["responses"]
        assert "200" in responses
        assert "401" in responses

    def test_response_description(self, spec_store):
        """Response description included."""
        result = get_endpoint_contract(spec_store, path="/users", method="GET")

        response_200 = result["responses"]["200"]
        assert response_200["description"] == "Success"

    def test_response_content(self, spec_store):
        """Response content with schema and example."""
        result = get_endpoint_contract(spec_store, path="/users", method="GET")

        content = result["responses"]["200"]["content"]
        assert "application/json" in content

        json_content = content["application/json"]
        assert "schema" in json_content
        assert "example" in json_content

    def test_response_headers(self, spec_store):
        """Response headers included."""
        result = get_endpoint_contract(spec_store, path="/users", method="GET")

        response_200 = result["responses"]["200"]
        assert "headers" in response_200
        assert "X-Total-Count" in response_200["headers"]

    def test_response_no_content(self, spec_store):
        """Response without content-type (e.g., 204 No Content)."""
        result = get_endpoint_contract(spec_store, path="/users", method="POST")

        response_400 = result["responses"].get("400", {})
        # 400 response only has description, no content


class TestErrorHandling:
    """Error handling and edge cases."""

    def test_endpoint_not_found(self, spec_store):
        """Raise KeyError if endpoint not found."""
        with pytest.raises(KeyError):
            get_endpoint_contract(spec_store, path="/nonexistent", method="GET")

    def test_method_not_found(self, spec_store):
        """Raise KeyError if method not found."""
        with pytest.raises(KeyError):
            get_endpoint_contract(spec_store, path="/users", method="PATCH")

    def test_unloaded_spec(self):
        """Raise KeyError if spec not loaded."""
        store = get_store()
        store.clear()

        with pytest.raises(KeyError):
            get_endpoint_contract(store, path="/users", method="GET")

    def test_method_case_insensitive(self, spec_store):
        """Method lookup is case-insensitive."""
        result1 = get_endpoint_contract(spec_store, path="/users", method="GET")
        result2 = get_endpoint_contract(spec_store, path="/users", method="get")

        assert result1["method"] == result2["method"] == "GET"


class TestIntegration:
    """Integration with SpecStore."""

    def test_contract_deep_copy(self, spec_store):
        """Contract is a deep copy (modifications don't affect spec)."""
        result = get_endpoint_contract(spec_store, path="/users", method="GET")

        # Modify the result
        result["parameters"].append({"name": "test", "in": "query"})
        result["responses"]["999"] = {"description": "Test"}

        # Get contract again - should not have modifications
        result2 = get_endpoint_contract(spec_store, path="/users", method="GET")

        assert len(result2["parameters"]) == 2  # Original count
        assert "999" not in result2["responses"]

    def test_multiple_methods_same_path(self, spec_store):
        """Get contracts for different methods on same path."""
        get_contract = get_endpoint_contract(spec_store, path="/users", method="GET")
        post_contract = get_endpoint_contract(spec_store, path="/users", method="POST")

        assert get_contract["operationId"] == "listUsers"
        assert post_contract["operationId"] == "createUser"
        assert get_contract != post_contract


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
