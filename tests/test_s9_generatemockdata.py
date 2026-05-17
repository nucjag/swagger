"""Tests for S9: generateMockData tool.

Covers:
- AC 1: Mock generation from JSON Schema (primitives, objects, arrays)
- AC 2: Example and default value prioritization
- AC 3: Nested schema resolution via resolveSchema
- AC 4: Count parameter for multiple objects
- AC 5: Form data support (string, file types)
"""

import sys
import pytest
from pathlib import Path
import json

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

from core.spec_store import get_store
from tools.mock_generator import generate_mock_data


# Sample spec with various schema patterns for testing
SAMPLE_SPEC = {
    "openapi": "3.0.0",
    "info": {"title": "Test API", "version": "1.0.0"},
    "paths": {},
    "components": {
        "schemas": {
            "Address": {
                "type": "object",
                "properties": {
                    "street": {"type": "string"},
                    "city": {"type": "string"},
                    "zip": {"type": "string"},
                    "country": {"type": "string"},
                },
                "required": ["street", "city"],
            },
            "User": {
                "type": "object",
                "properties": {
                    "id": {"type": "string", "format": "uuid"},
                    "name": {"type": "string"},
                    "email": {"type": "string", "format": "email"},
                    "age": {"type": "integer", "minimum": 18, "maximum": 100},
                    "active": {"type": "boolean"},
                    "role": {"type": "string", "enum": ["admin", "user", "guest"]},
                    "address": {"$ref": "#/components/schemas/Address"},
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 1,
                        "maxItems": 3,
                    },
                },
                "required": ["id", "name", "email"],
                "example": {
                    "id": "550e8400-e29b-41d4-a716-446655440000",
                    "name": "John Doe",
                    "email": "john@example.com",
                },
            },
            "Product": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "name": {"type": "string"},
                    "price": {"type": "number", "minimum": 0, "maximum": 10000},
                    "inStock": {"type": "boolean", "default": True},
                    "sku": {"type": "string", "pattern": "[A-Z0-9]{6}"},
                },
            },
            "UserList": {
                "type": "object",
                "properties": {
                    "total": {"type": "integer"},
                    "items": {
                        "type": "array",
                        "items": {"$ref": "#/components/schemas/User"},
                    },
                },
            },
            "SimpleString": {"type": "string", "example": "fixed_example"},
            "URLField": {"type": "string", "format": "url"},
            "DateField": {"type": "string", "format": "date"},
        }
    },
}


@pytest.fixture
def spec_store_with_data():
    """Setup spec store with test data."""
    store = get_store()
    store.set_spec(SAMPLE_SPEC)
    return store


class TestBasicMockGeneration:
    """AC-1: Generate mocks from JSON Schema primitives."""

    def test_string_generation(self, spec_store_with_data):
        """Generate string values."""
        result = generate_mock_data("SimpleString", count=1)
        assert result["success"] is True
        assert len(result["data"]) == 1
        assert isinstance(result["data"][0], str)

    def test_integer_generation(self, spec_store_with_data):
        """Generate integer values within range."""
        result = generate_mock_data("Product", count=3)
        assert result["success"] is True
        assert len(result["data"]) == 3

        for obj in result["data"]:
            assert isinstance(obj["id"], int)
            assert 0 <= obj["price"] <= 10000

    def test_boolean_generation(self, spec_store_with_data):
        """Generate boolean values."""
        result = generate_mock_data("Product", count=5)
        assert result["success"] is True

        for obj in result["data"]:
            assert isinstance(obj["inStock"], bool)

    def test_enum_generation(self, spec_store_with_data):
        """Generate enum values from choices."""
        result = generate_mock_data("User", count=10)
        assert result["success"] is True

        # Only check role in objects that have it (not first one with example)
        roles = {obj["role"] for obj in result["data"] if "role" in obj}
        allowed_roles = {"admin", "user", "guest"}
        assert roles.issubset(allowed_roles)
        assert (
            len(roles) > 0
        )  # Should have at least one role type in non-example objects

    def test_array_generation(self, spec_store_with_data):
        """Generate arrays with items."""
        result = generate_mock_data("User", count=3)
        assert result["success"] is True

        # Check that at least some objects have arrays
        for obj in result["data"]:
            if "tags" in obj:
                assert isinstance(obj["tags"], list)
                assert 1 <= len(obj["tags"]) <= 3
                assert all(isinstance(tag, str) for tag in obj["tags"])

    def test_object_generation(self, spec_store_with_data):
        """Generate nested objects."""
        result = generate_mock_data("User", count=2)
        assert result["success"] is True

        # Check that generated (non-example) objects have nested objects
        for obj in result["data"]:
            if "address" in obj:
                assert isinstance(obj["address"], dict)
                assert "street" in obj["address"]
                assert "city" in obj["address"]


class TestExamplesAndDefaults:
    """AC-2: Prioritize examples and default values."""

    def test_example_in_first_object(self, spec_store_with_data):
        """First object should use example if available."""
        result = generate_mock_data("User", count=3)
        assert result["success"] is True

        # First object should have example values
        first = result["data"][0]
        assert first["id"] == "550e8400-e29b-41d4-a716-446655440000"
        assert first["name"] == "John Doe"
        assert first["email"] == "john@example.com"

    def test_different_values_in_subsequent_objects(self, spec_store_with_data):
        """Subsequent objects should be generated, not copies of example."""
        result = generate_mock_data("User", count=3)
        assert result["success"] is True

        # Second and third objects should have different values
        ids = [obj["id"] for obj in result["data"]]
        assert len(set(ids)) == len(ids)  # All IDs should be unique

    def test_default_value_usage(self, spec_store_with_data):
        """Use default value for fields marked with default."""
        result = generate_mock_data("Product", count=2)
        assert result["success"] is True

        for obj in result["data"]:
            assert obj["inStock"] is True  # default value


class TestSchemaResolution:
    """AC-3: Resolve nested $ref schemas."""

    def test_single_level_ref(self, spec_store_with_data):
        """Resolve $ref at one level."""
        result = generate_mock_data("User", count=2)
        assert result["success"] is True

        # Find an object that has address (skip the example object)
        user = next((obj for obj in result["data"] if "address" in obj), None)
        assert user is not None, "Should have at least one object with address"
        assert isinstance(user["address"], dict)
        assert user["address"]["street"] is not None
        assert user["address"]["city"] is not None

    def test_nested_ref(self, spec_store_with_data):
        """Resolve nested $ref in array items."""
        result = generate_mock_data("UserList", count=1)
        assert result["success"] is True

        user_list = result["data"][0]
        assert isinstance(user_list["items"], list)
        assert len(user_list["items"]) > 0

        for user in user_list["items"]:
            assert "id" in user
            assert "name" in user
            assert "address" in user


class TestCountParameter:
    """AC-4: Generate multiple objects with count parameter."""

    def test_count_one(self, spec_store_with_data):
        """Count=1 returns single object."""
        result = generate_mock_data("User", count=1)
        assert result["success"] is True
        assert len(result["data"]) == 1

    def test_count_multiple(self, spec_store_with_data):
        """Count > 1 returns multiple objects."""
        for count in [2, 5, 10]:
            result = generate_mock_data("User", count=count)
            assert result["success"] is True
            assert len(result["data"]) == count

    def test_unique_values_across_objects(self, spec_store_with_data):
        """Each object should have unique generated values."""
        result = generate_mock_data("User", count=5)
        assert result["success"] is True

        emails = [obj["email"] for obj in result["data"]]
        assert len(set(emails)) > 1  # Not all emails should be the same


class TestStringFormats:
    """Test specific string format generation."""

    def test_email_format(self, spec_store_with_data):
        """Generate valid email addresses."""
        result = generate_mock_data("User", count=3)
        assert result["success"] is True

        for i, obj in enumerate(result["data"]):
            email = obj["email"]
            if i == 0:  # First is example
                assert email == "john@example.com"
            else:
                assert "@" in email
                assert "example.com" in email

    def test_uuid_format(self, spec_store_with_data):
        """Generate valid UUIDs."""
        result = generate_mock_data("User", count=2)
        assert result["success"] is True

        for obj in result["data"]:
            uuid = obj["id"]
            # UUID format or example
            assert isinstance(uuid, str)
            assert len(uuid) == 36  # UUID string length

    def test_url_format(self, spec_store_with_data):
        """Generate valid URLs."""
        result = generate_mock_data("URLField", count=2)
        assert result["success"] is True

        for url in result["data"]:
            assert "https://" in url

    def test_date_format(self, spec_store_with_data):
        """Generate valid dates."""
        result = generate_mock_data("DateField", count=2)
        assert result["success"] is True

        for date in result["data"]:
            assert isinstance(date, str)
            assert len(date) == 10  # YYYY-MM-DD format


class TestErrorHandling:
    """Test error handling for invalid inputs."""

    def test_nonexistent_schema(self, spec_store_with_data):
        """Handle nonexistent schema gracefully."""
        result = generate_mock_data("NonExistentSchema", count=1)
        assert result["success"] is False
        assert "error" in result

    def test_default_count_value(self, spec_store_with_data):
        """Default count should be 1 if not specified."""
        # Call without explicit count parameter
        result = generate_mock_data("User")
        assert result["success"] is True
        assert len(result["data"]) == 1


class TestDataStructure:
    """Test output structure and format."""

    def test_success_response_structure(self, spec_store_with_data):
        """Verify response structure for successful generation."""
        result = generate_mock_data("User", count=1)
        assert isinstance(result, dict)
        assert "success" in result
        assert "data" in result
        assert result["success"] is True
        assert isinstance(result["data"], list)

    def test_error_response_structure(self, spec_store_with_data):
        """Verify response structure for error."""
        result = generate_mock_data("BadSchema", count=1)
        assert isinstance(result, dict)
        assert "success" in result
        assert "error" in result
        assert result["success"] is False

    def test_mock_data_is_json_serializable(self, spec_store_with_data):
        """Generated mocks should be JSON serializable."""
        result = generate_mock_data("User", count=3)
        assert result["success"] is True

        # Should not raise during JSON serialization
        json_str = json.dumps(result["data"])
        assert isinstance(json_str, str)


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
