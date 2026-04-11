"""
Tests for validateRequest tool (S10).

Tests validation of request data against endpoint contracts.
"""

import pytest
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.validator import validate_request
from core.spec_store import get_store


# Sample spec for testing
SAMPLE_SPEC = {
    "openapi": "3.0.0",
    "info": {"title": "Test API", "version": "1.0.0"},
    "paths": {
        "/users": {
            "post": {
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string", "minLength": 2},
                                    "email": {"type": "string", "format": "email"},
                                    "age": {"type": "integer", "minimum": 0, "maximum": 150},
                                    "status": {
                                        "type": "string",
                                        "enum": ["active", "inactive"],
                                    },
                                    "address": {
                                        "type": "object",
                                        "properties": {
                                            "street": {"type": "string"},
                                            "zip": {"type": "string"},
                                        },
                                    },
                                    "tags": {
                                        "type": "array",
                                        "items": {"type": "string"},
                                        "minItems": 1,
                                        "maxItems": 5,
                                    },
                                },
                                "required": ["name", "email"],
                            }
                        }
                    },
                }
            }
        },
        "/users/{id}": {
            "put": {
                "requestBody": {
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string"},
                                    "age": {"type": "integer", "minimum": 0, "maximum": 150},
                                    "status": {
                                        "type": "string",
                                        "enum": ["active", "inactive"],
                                    },
                                },
                            }
                        }
                    }
                }
            }
        },
        "/register": {
            "post": {
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "email": {"type": "string", "format": "email"},
                                    "password": {
                                        "type": "string",
                                        "minLength": 8,
                                    },
                                },
                                "required": ["email", "password"],
                            }
                        }
                    },
                }
            }
        },
        "/posts": {
            "post": {
                "requestBody": {
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "title": {"type": "string"},
                                    "tags": {
                                        "type": "array",
                                        "items": {"type": "string"},
                                        "minItems": 1,
                                    },
                                },
                            }
                        }
                    }
                }
            }
        },
    },
    "components": {"schemas": {}},
}


class TestValidateRequest:
    """Test validateRequest tool."""

    @pytest.fixture(autouse=True)
    def setup_spec(self):
        """Load test spec before each test."""
        store = get_store()
        store.set_spec(SAMPLE_SPEC)

    def test_validate_basic_types_string(self):
        """AC 1: Validate string type."""
        result = validate_request(
            path="/users",
            method="POST",
            data={"name": "John", "email": "john@example.com"},
        )
        assert result["valid"] is True
        assert result["errors"] == []

    def test_validate_basic_types_integer_error(self):
        """AC 1: Detect integer type mismatch."""
        result = validate_request(
            path="/users/{id}",
            method="PUT",
            data={"age": "not a number"},
        )
        assert result["valid"] is False
        assert any("age" in err["path"] for err in result["errors"])

    def test_required_fields_missing(self):
        """AC 2: Detect missing required fields."""
        result = validate_request(
            path="/register",
            method="POST",
            data={"email": "test@example.com"},
        )
        assert result["valid"] is False
        assert any("password" in err["path"] for err in result["errors"])

    def test_required_fields_present(self):
        """AC 2: Accept all required fields."""
        result = validate_request(
            path="/register",
            method="POST",
            data={"email": "test@example.com", "password": "secret123"},
        )
        errors_on_required = [
            err
            for err in result["errors"]
            if "required field missing" in err["message"]
        ]
        assert len(errors_on_required) == 0

    def test_enum_validation_valid(self):
        """AC 3: Accept valid enum value."""
        result = validate_request(
            path="/users/{id}",
            method="PUT",
            data={"status": "active"},
        )
        errors_on_enum = [err for err in result["errors"] if "enum" in err["message"]]
        assert len(errors_on_enum) == 0

    def test_enum_validation_invalid(self):
        """AC 3: Reject invalid enum value."""
        result = validate_request(
            path="/users/{id}",
            method="PUT",
            data={"status": "banned"},
        )
        assert result["valid"] is False
        assert any("enum" in err["message"] for err in result["errors"])

    def test_nested_object_validation(self):
        """AC 4: Validate nested object properties."""
        result = validate_request(
            path="/users",
            method="POST",
            data={
                "name": "John",
                "email": "john@example.com",
                "address": {"zip": 12345},
            },
        )
        assert result["valid"] is False
        assert any(
            "address" in err["path"] and "zip" in err["path"]
            for err in result["errors"]
        )

    def test_nested_object_valid(self):
        """AC 4: Accept valid nested object."""
        result = validate_request(
            path="/users",
            method="POST",
            data={
                "name": "John",
                "email": "john@example.com",
                "address": {"zip": "12345"},
            },
        )
        nested_errors = [
            err
            for err in result["errors"]
            if "address" in err["path"] and "zip" in err["path"]
        ]
        assert len(nested_errors) == 0

    def test_array_items_validation(self):
        """AC 5: Validate array item types."""
        result = validate_request(
            path="/posts",
            method="POST",
            data={
                "title": "Test",
                "tags": [1, 2, "ok"],
            },
        )
        assert result["valid"] is False
        assert any("tags[0]" in err["path"] for err in result["errors"])
        assert any("tags[1]" in err["path"] for err in result["errors"])

    def test_array_items_valid(self):
        """AC 5: Accept valid array items."""
        result = validate_request(
            path="/posts",
            method="POST",
            data={
                "title": "Test",
                "tags": ["python", "testing", "api"],
            },
        )
        array_errors = [
            err for err in result["errors"] if "tags[" in err["path"]
        ]
        assert len(array_errors) == 0

    def test_min_length_string(self):
        """AC 8: Validate string min length."""
        result = validate_request(
            path="/register",
            method="POST",
            data={"email": "test@example.com", "password": "short"},
        )
        assert result["valid"] is False
        assert any("minimum length" in err["message"] for err in result["errors"])

    def test_numeric_bounds(self):
        """AC 8: Validate numeric min/max bounds."""
        result = validate_request(
            path="/users",
            method="POST",
            data={"name": "John", "email": "john@example.com", "age": 200},
        )
        assert result["valid"] is False
        assert any("maximum" in err["message"] for err in result["errors"])

    def test_success_case_all_valid(self):
        """AC 7: Return valid=True for correct data."""
        result = validate_request(
            path="/users",
            method="POST",
            data={
                "name": "Alice",
                "email": "alice@example.com",
            },
        )
        assert result["valid"] is True
        assert result["errors"] == []

    def test_validation_error_format(self):
        """Test that error format matches spec."""
        result = validate_request(
            path="/users",
            method="POST",
            data={"age": "invalid"},
        )
        if not result["valid"]:
            for error in result["errors"]:
                assert isinstance(error, dict)
                assert "path" in error
                assert "message" in error
                assert isinstance(error["path"], str)
                assert isinstance(error["message"], str)

    def test_array_min_items(self):
        """Test array minItems validation."""
        result = validate_request(
            path="/posts",
            method="POST",
            data={
                "title": "Test",
                "tags": [],
            },
        )
        assert result["valid"] is False
        assert any("minimum items" in err["message"] for err in result["errors"])


class TestValidateRequestIntegration:
    """Integration tests with real endpoint contracts."""

    @pytest.fixture(autouse=True)
    def setup_spec(self):
        """Load test spec before each test."""
        store = get_store()
        store.set_spec(SAMPLE_SPEC)

    def test_post_user_full_validation(self):
        """Test full validation for POST /users endpoint."""
        valid_data = {
            "name": "John Doe",
            "email": "john@example.com",
            "age": 30,
        }
        result = validate_request(
            path="/users",
            method="POST",
            data=valid_data,
        )
        assert result["valid"] is True

    def test_validation_multiple_errors(self):
        """Test that multiple validation errors are all reported."""
        bad_data = {
            "name": "J",
            "age": 200,
        }
        result = validate_request(
            path="/users",
            method="POST",
            data=bad_data,
        )
        assert result["valid"] is False
        assert len(result["errors"]) > 0
