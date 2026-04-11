"""
Tests for code generation tools (S7).

Tests cover AC-1 through AC-5 for generateClient functionality.
"""

import pytest
from typing import Dict, Any

# Import classes to test
from tools.codegen import (
    TypeScriptTypeGenerator,
    ParameterExtractor,
    FetchFunctionGenerator,
    CodeGenerator,
)


class MockSpecStore:
    """Mock spec store for testing."""

    def __init__(self, spec: Dict[str, Any] = None):
        self.spec = spec or {}

    def resolve_schema(self, ref: str) -> Dict[str, Any]:
        """Mock schema resolution."""
        if ref == "#/components/schemas/User":
            return {
                "type": "object",
                "properties": {
                    "id": {"type": "number"},
                    "name": {"type": "string"},
                    "email": {"type": "string"},
                },
                "required": ["id", "name"],
            }
        elif ref == "#/components/schemas/Profile":
            return {
                "type": "object",
                "properties": {"name": {"type": "string"}, "bio": {"type": "string"}},
            }
        return {}

    def get_endpoint_contract(self, endpoint_id: int) -> Dict[str, Any]:
        """Mock endpoint contract retrieval."""
        contracts = {
            1: {  # GET /users
                "path": "/users",
                "method": "GET",
                "operationId": "listUsers",
                "parameters": [],
                "responses": {
                    "200": {
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "array",
                                    "items": {"$ref": "#/components/schemas/User"},
                                }
                            }
                        }
                    }
                },
            },
            2: {  # POST /users
                "path": "/users",
                "method": "POST",
                "operationId": "createUser",
                "parameters": [],
                "requestBody": {
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string"},
                                    "email": {"type": "string"},
                                },
                                "required": ["name", "email"],
                            }
                        }
                    }
                },
                "responses": {
                    "201": {
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/User"}
                            }
                        }
                    }
                },
            },
            3: {  # GET /users/{id}
                "path": "/users/{id}",
                "method": "GET",
                "operationId": "getUser",
                "parameters": [
                    {
                        "name": "id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string"},
                    }
                ],
                "responses": {
                    "200": {
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/User"}
                            }
                        }
                    }
                },
            },
        }
        return contracts.get(endpoint_id, {})


# ============================================================================
# AC-1: Type Generation Tests
# ============================================================================


class TestTypeGeneration:
    """Tests for AC-1: Generating TypeScript types from schemas."""

    def test_generate_types_simple_object(self):
        """AC-1: Generate types for simple object."""
        spec_store = MockSpecStore()
        type_gen = TypeScriptTypeGenerator(spec_store)

        schema = {
            "type": "object",
            "properties": {"id": {"type": "number"}, "name": {"type": "string"}},
        }

        result = type_gen.schema_to_typescript(schema, "SimpleUser")

        assert "type SimpleUser" in result
        assert "id" in result
        assert "name" in result
        assert "number" in result
        assert "string" in result

    def test_generate_types_optional_fields(self):
        """AC-1: Optional fields should be marked with ?"""
        spec_store = MockSpecStore()
        type_gen = TypeScriptTypeGenerator(spec_store)

        schema = {
            "type": "object",
            "properties": {
                "id": {"type": "number"},
                "name": {"type": "string"},
                "bio": {"type": "string"},
            },
            "required": ["id", "name"],
        }

        result = type_gen._build_type(schema)

        # bio should be optional
        assert "bio?" in result
        # id and name should be required
        assert "id:" in result or "id}:" in result

    def test_generate_types_array(self):
        """AC-1: Generate array types."""
        spec_store = MockSpecStore()
        type_gen = TypeScriptTypeGenerator(spec_store)

        schema = {"type": "array", "items": {"type": "string"}}

        result = type_gen._build_type(schema)

        assert "string[]" in result

    def test_generate_types_enum(self):
        """AC-1: Generate enum as union type."""
        spec_store = MockSpecStore()
        type_gen = TypeScriptTypeGenerator(spec_store)

        schema = {"type": "string", "enum": ["active", "inactive", "pending"]}

        result = type_gen._build_type(schema)

        assert "'active'" in result
        assert "'inactive'" in result
        assert "'pending'" in result
        assert "|" in result


# ============================================================================
# AC-2: Fetch Function Generation Tests
# ============================================================================


class TestFetchFunctionGeneration:
    """Tests for AC-2: Generating fetch functions with typing."""

    def test_generate_simple_get_function(self):
        """AC-2: Generate simple GET function."""
        spec_store = MockSpecStore()
        fetch_gen = FetchFunctionGenerator(spec_store)

        contract = {
            "method": "GET",
            "path": "/users",
            "operationId": "listUsers",
            "parameters": [],
            "responses": {"200": {}},
        }

        result = fetch_gen.generate(contract, "listUsers")

        assert "async function listUsers" in result
        assert "fetch" in result
        assert "Promise" in result

    def test_generate_post_function_with_body(self):
        """AC-2: Generate POST function with body parameter."""
        spec_store = MockSpecStore()
        fetch_gen = FetchFunctionGenerator(spec_store)

        contract = {
            "method": "POST",
            "path": "/users",
            "operationId": "createUser",
            "parameters": [],
            "requestBody": {
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "properties": {"name": {"type": "string"}},
                        }
                    }
                }
            },
            "responses": {"201": {}},
        }

        result = fetch_gen.generate(contract, "createUser")

        assert "async function createUser" in result
        assert "POST" in result
        assert "JSON.stringify" in result


# ============================================================================
# AC-3: HTTP Methods Support Tests
# ============================================================================


class TestHTTPMethodsSupport:
    """Tests for AC-3: Support for different HTTP methods."""

    @pytest.mark.parametrize("method", ["GET", "POST", "PUT", "DELETE", "PATCH"])
    def test_all_http_methods_supported(self, method):
        """AC-3: All HTTP methods should be supported."""
        spec_store = MockSpecStore()
        fetch_gen = FetchFunctionGenerator(spec_store)

        contract = {
            "method": method,
            "path": "/resource",
            "operationId": f"{method.lower()}Resource",
            "parameters": [],
            "responses": {"200": {}},
        }

        result = fetch_gen.generate(contract, f"{method.lower()}Resource")

        assert f"'{method}'" in result or f'"{method}"' in result


# ============================================================================
# AC-4: Parameter Handling Tests
# ============================================================================


class TestParameterHandling:
    """Tests for AC-4: Path, query, and body parameter handling."""

    def test_path_params_extraction(self):
        """AC-4: Extract path parameters."""
        spec_store = MockSpecStore()
        param_ext = ParameterExtractor(spec_store)

        endpoint = {
            "path": "/users/{id}/posts/{postId}",
            "parameters": [],
            "requestBody": {},
        }

        result = param_ext.extract_all(endpoint)

        assert "id" in result["path_params"]
        assert "postId" in result["path_params"]

    def test_query_params_extraction(self):
        """AC-4: Extract query parameters."""
        spec_store = MockSpecStore()
        param_ext = ParameterExtractor(spec_store)

        endpoint = {
            "path": "/users",
            "parameters": [
                {"name": "limit", "in": "query", "schema": {"type": "number"}},
                {"name": "offset", "in": "query", "schema": {"type": "number"}},
            ],
            "requestBody": {},
        }

        result = param_ext.extract_all(endpoint)

        assert "limit" in result["query_params"]
        assert "offset" in result["query_params"]

    def test_body_params_extraction(self):
        """AC-4: Extract body parameters."""
        spec_store = MockSpecStore()
        param_ext = ParameterExtractor(spec_store)

        endpoint = {
            "path": "/users",
            "parameters": [],
            "requestBody": {
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "email": {"type": "string"},
                            },
                        }
                    }
                }
            },
        }

        result = param_ext.extract_all(endpoint)

        assert "name" in result["body_params"]
        assert "email" in result["body_params"]


# ============================================================================
# AC-5: Ready-to-Paste Code Tests
# ============================================================================


class TestReadyToPasteCode:
    """Tests for AC-5: Code should be ready to paste without external deps."""

    def test_no_external_dependencies(self):
        """AC-5: Generated code should not require external dependencies."""
        spec_store = MockSpecStore()
        codegen = CodeGenerator(spec_store)

        result = codegen.generate_client([1])

        # Should not have imports for axios, http, etc
        assert "import axios" not in result
        assert "import http" not in result
        assert "import fetch from" not in result  # fetch is native

    def test_uses_native_fetch(self):
        """AC-5: Generated code should use native fetch API."""
        spec_store = MockSpecStore()
        codegen = CodeGenerator(spec_store)

        result = codegen.generate_client([1])

        # Should use fetch (native API available in Node 18+ and browsers)
        assert "fetch(" in result or "fetch " in result

    def test_typescript_types_generated(self):
        """AC-5: Code should include TypeScript type definitions."""
        spec_store = MockSpecStore()
        codegen = CodeGenerator(spec_store)

        result = codegen.generate_client([1], include=["types", "fetch"])

        # Should have type or interface definitions
        assert "type " in result or "interface " in result

    def test_multiple_endpoints_in_single_file(self):
        """AC-5: Multiple endpoints should be in single file with all types."""
        spec_store = MockSpecStore()
        codegen = CodeGenerator(spec_store)

        result = codegen.generate_client([1, 2], include=["types", "fetch"])

        # Should have multiple function definitions
        assert "function" in result


# ============================================================================
# Integration Tests
# ============================================================================


class TestIntegration:
    """Integration tests for complete generateClient flow."""

    def test_full_workflow_single_endpoint(self):
        """Full workflow: types + fetch for single GET endpoint."""
        spec_store = MockSpecStore()
        codegen = CodeGenerator(spec_store)

        result = codegen.generate_client([1])

        assert result is not None
        assert len(result) > 0
        assert "function" in result

    def test_full_workflow_multiple_endpoints(self):
        """Full workflow: types + fetch for multiple endpoints."""
        spec_store = MockSpecStore()
        codegen = CodeGenerator(spec_store)

        result = codegen.generate_client([1, 2, 3])

        assert result is not None
        assert len(result) > 0
        # Should have at least a few hundred characters
        assert len(result) > 100


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
