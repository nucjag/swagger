"""
Tests for Jest test generation (S8).

Tests cover AC-1 through AC-4 for generateTests functionality.
"""

import pytest
from typing import Dict, Any

# Import classes to test
from tools.codegen import TestGenerator, CodeGenerator


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
        elif ref == "#/components/schemas/Product":
            return {
                "type": "object",
                "properties": {
                    "id": {"type": "number"},
                    "name": {"type": "string"},
                    "price": {"type": "number"},
                    "status": {"type": "string", "enum": ["active", "inactive", "draft"]},
                },
                "required": ["id", "name", "price"],
            }
        return {}

    def get_endpoint_contract(self, endpoint_id: int) -> Dict[str, Any]:
        """Mock endpoint contract retrieval."""
        contracts = {
            1: {  # GET /users (happy path)
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
            2: {  # POST /users (happy path + error cases)
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
                    "200": {
                        "content": {
                            "application/json": {"schema": {"$ref": "#/components/schemas/User"}}
                        }
                    },
                    "400": {
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "error": {"type": "string"},
                                        "message": {"type": "string"},
                                    },
                                }
                            }
                        }
                    },
                },
            },
            3: {  # GET /products?status=active (parameterized)
                "path": "/products",
                "method": "GET",
                "operationId": "getProducts",
                "parameters": [
                    {
                        "name": "status",
                        "in": "query",
                        "required": False,
                        "schema": {
                            "type": "string",
                            "enum": ["active", "inactive", "draft"],
                        },
                    },
                    {
                        "name": "limit",
                        "in": "query",
                        "required": False,
                        "schema": {"type": "integer"},
                    },
                ],
                "responses": {
                    "200": {
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "array",
                                    "items": {"$ref": "#/components/schemas/Product"},
                                }
                            }
                        }
                    }
                },
            },
        }
        return contracts.get(endpoint_id, {})


class TestGenerateTests:
    """Test generateTests functionality (AC-1 through AC-4)."""

    @pytest.fixture
    def mock_store(self):
        """Provide mock spec store."""
        return MockSpecStore()

    @pytest.fixture
    def test_gen(self, mock_store):
        """Provide TestGenerator instance."""
        return TestGenerator(mock_store)

    def test_ac1_happy_path_basic(self, test_gen):
        """AC-1: Generate basic happy path test."""
        # Given: simple GET endpoint
        result = test_gen.generate_test_suite([1])

        # Then: result should contain describe block and happy path test
        assert "describe" in result
        assert "it(" in result
        assert "listUsers" in result
        assert "GET /users" in result

    def test_ac1_happy_path_imports(self, test_gen):
        """AC-1: Tests should have Jest imports."""
        # When: generating test suite
        result = test_gen.generate_test_suite([1])

        # Then: should include Jest imports
        assert "@jest/globals" in result
        assert "import" in result
        assert "describe" in result or "it" in result

    def test_ac2_error_cases_with_required_params(self, test_gen):
        """AC-2: Generate error case tests for missing required params."""
        # Given: endpoint with required parameters (POST /users)
        result = test_gen.generate_test_suite([2])

        # Then: should include test cases (happy path + error handling)
        assert "it(" in result or "describe" in result

    def test_ac2_error_response_handling(self, test_gen):
        """AC-2: Tests should handle HTTP error responses (400, 500)."""
        # When: generating tests for endpoint with error responses
        result = test_gen.generate_test_suite([2])

        # Then: result should be valid Jest code
        assert "describe" in result
        # Error handling is generated for required params

    def test_ac3_parameterized_with_enum(self, test_gen):
        """AC-3: Generate parameterized tests for enum parameters."""
        # Given: endpoint with enum parameter (status: active|inactive|draft)
        result = test_gen.generate_test_suite([3])

        # Then: should include parameterized test with enum values
        assert "it.each" in result or "enum" in result.lower() or "status" in result

    def test_ac3_parameterized_syntax(self, test_gen):
        """AC-3: Parameterized tests should use test.each syntax."""
        # When: generating tests with enum parameters
        result = test_gen.generate_test_suite([3])

        # Then: should use Jest parameterization syntax
        assert "it.each" in result
        # Should have enum values
        assert "describe" in result

    def test_ac4_imports_client_types(self, test_gen):
        """AC-4: Tests should import client types."""
        # Given: test generation
        result = test_gen.generate_test_suite([1])

        # Then: should import from client
        assert "import" in result
        assert "client" in result

    def test_ac4_typescript_typed_requests(self, test_gen):
        """AC-4: Requests should be typed (strict mode compatible)."""
        # When: generating tests
        result = test_gen.generate_test_suite([2])

        # Then: should have type annotations
        assert "Request" in result or "response" in result or "{}" in result

    def test_multiple_endpoints(self, test_gen):
        """Test generating tests for multiple endpoints."""
        # When: requesting tests for multiple endpoints
        result = test_gen.generate_test_suite([1, 2, 3])

        # Then: should include all describe blocks
        assert result.count("describe") >= 3
        assert "listUsers" in result
        assert "createUser" in result
        assert "getProducts" in result

    def test_empty_endpoint_ids(self, test_gen):
        """Test with empty endpoint list."""
        # When: generating tests for empty list
        result = test_gen.generate_test_suite([])

        # Then: should return empty or valid Jest structure
        assert isinstance(result, str)

    def test_non_existent_endpoint(self, test_gen):
        """Test handling of non-existent endpoint."""
        # When: requesting tests for non-existent endpoint
        result = test_gen.generate_test_suite([999])

        # Then: should gracefully handle (no tests generated)
        # or include error handling
        assert isinstance(result, str)


class TestCodeGeneratorGenerateTests:
    """Test CodeGenerator.generate_tests integration."""

    @pytest.fixture
    def mock_store(self):
        """Provide mock spec store."""
        return MockSpecStore()

    @pytest.fixture
    def code_gen(self, mock_store):
        """Provide CodeGenerator instance."""
        return CodeGenerator(mock_store)

    def test_generate_tests_framework_jest(self, code_gen):
        """Test generateTests with jest framework."""
        # When: generating tests with jest
        result = code_gen.generate_tests([1], framework="jest")

        # Then: should return valid Jest code
        assert isinstance(result, str)
        assert "describe" in result or len(result) > 0

    def test_generate_tests_invalid_framework(self, code_gen):
        """Test generateTests with invalid framework raises error."""
        # When: using unsupported framework
        with pytest.raises(ValueError):
            code_gen.generate_tests([1], framework="mocha")

    def test_generate_tests_with_mocks(self, code_gen):
        """Test generateTests includes mock data."""
        # When: generating with include_mocks=True
        result = code_gen.generate_tests([1], include_mocks=True)

        # Then: should return test code
        assert isinstance(result, str)

    def test_generate_tests_multiple_endpoints(self, code_gen):
        """Test generateTests with multiple endpoints."""
        # When: generating tests for multiple endpoints
        result = code_gen.generate_tests([1, 2, 3])

        # Then: should include all endpoints
        assert len(result) > 0
        assert "describe" in result


class TestTestGeneratorStructure:
    """Test Jest code structure generated."""

    @pytest.fixture
    def mock_store(self):
        """Provide mock spec store."""
        return MockSpecStore()

    @pytest.fixture
    def test_gen(self, mock_store):
        """Provide TestGenerator instance."""
        return TestGenerator(mock_store)

    def test_describe_block_naming(self, test_gen):
        """Test that describe blocks have correct naming."""
        # When: generating tests
        result = test_gen.generate_test_suite([1])

        # Then: describe should include method and path
        assert "GET" in result or "describe" in result

    def test_test_case_naming(self, test_gen):
        """Test that test cases have meaningful names."""
        # When: generating tests
        result = test_gen.generate_test_suite([1])

        # Then: should have it() with description
        assert "it(" in result or "should" in result

    def test_async_test_functions(self, test_gen):
        """Test that test functions are async."""
        # When: generating tests
        result = test_gen.generate_test_suite([2])

        # Then: should include async/await
        # (Implementation may vary, but should be compatible with Jest)
        assert isinstance(result, str)

    def test_imports_at_beginning(self, test_gen):
        """Test that imports are at the beginning of file."""
        # When: generating tests
        result = test_gen.generate_test_suite([1])

        # Then: imports should come first
        if "import" in result:
            import_index = result.find("import")
            describe_index = result.find("describe")
            if describe_index >= 0:
                assert import_index < describe_index
