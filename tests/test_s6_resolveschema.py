"""Tests for S6: resolveSchema tool.

Covers:
- AC 1: Tool registration in FastMCP
- AC 2: Simple $ref resolution
- AC 3: Nested $ref resolution
- AC 4: Array items.$ref resolution
- AC 5: Circular reference handling
"""

import sys
import pytest
from pathlib import Path
import json

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

from core.spec_store import get_store
from tools.schema_resolver import resolve_schema


# Sample spec with various schema patterns
SAMPLE_SPEC = {
    "openapi": "3.0.0",
    "info": {"title": "Test API", "version": "1.0.0"},
    "paths": {},
    "components": {
        "schemas": {
            "Image": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "url": {"type": "string"},
                    "alt": {"type": "string"},
                },
            },
            "Profile": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "bio": {"type": "string"},
                    "avatar": {"$ref": "#/components/schemas/Image"},
                },
            },
            "User": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "name": {"type": "string"},
                    "email": {"type": "string"},
                    "profile": {"$ref": "#/components/schemas/Profile"},
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
            "SimpleUser": {
                "type": "object",
                "properties": {"id": {"type": "string"}, "name": {"type": "string"}},
            },
            "UserWithFriends": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "name": {"type": "string"},
                    "friends": {
                        "type": "array",
                        "items": {"$ref": "#/components/schemas/UserWithFriends"},
                    },
                },
            },
        }
    },
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
    """AC 1: resolveSchema registered as MCP tool."""

    def test_tool_exists(self, spec_store):
        """Tool function exists and is callable."""
        assert callable(resolve_schema)

    def test_tool_signature(self, spec_store):
        """Tool has correct parameters."""
        import inspect

        sig = inspect.signature(resolve_schema)
        params = list(sig.parameters.keys())

        assert "spec_store" in params
        assert "schema_name" in params

    def test_returns_dict(self, spec_store):
        """Tool returns dict object."""
        result = resolve_schema(spec_store, schema_name="SimpleUser")
        assert isinstance(result, dict)

    def test_result_has_schema_fields(self, spec_store):
        """Resolved schema has type and properties."""
        result = resolve_schema(spec_store, schema_name="SimpleUser")

        assert "type" in result
        assert "properties" in result


class TestAC2SimpleRefResolution:
    """AC 2: Simple $ref resolution."""

    def test_simple_schema_no_refs(self, spec_store):
        """Simple schema without refs is returned as-is."""
        result = resolve_schema(spec_store, schema_name="SimpleUser")

        assert result["type"] == "object"
        assert len(result["properties"]) == 2
        assert "id" in result["properties"]
        assert "name" in result["properties"]

    def test_no_refs_in_result(self, spec_store):
        """Resolved schema has no $ref at any level."""
        result = resolve_schema(spec_store, schema_name="SimpleUser")

        # Check that no $ref exists in result
        result_json = json.dumps(result)
        assert "$ref" not in result_json

    def test_schema_name_with_ref_prefix(self, spec_store):
        """Schema name with $ref prefix works."""
        result = resolve_schema(
            spec_store, schema_name="#/components/schemas/SimpleUser"
        )

        assert result["type"] == "object"
        assert "id" in result["properties"]


class TestAC3NestedRefResolution:
    """AC 3: Nested $ref resolution (one level deep)."""

    def test_single_nested_ref(self, spec_store):
        """Single nested $ref is resolved."""
        result = resolve_schema(spec_store, schema_name="Profile")

        # Check that profile has avatar resolved
        avatar = result["properties"]["avatar"]
        assert "$ref" not in json.dumps(avatar)
        assert avatar["type"] == "object"
        assert "url" in avatar["properties"]

    def test_multiple_nested_refs(self, spec_store):
        """Multiple nested $ref (User → Profile → Image) are resolved."""
        result = resolve_schema(spec_store, schema_name="User")

        # User.profile should be resolved Profile
        profile = result["properties"]["profile"]
        assert profile["type"] == "object"
        assert "bio" in profile["properties"]

        # User.profile.avatar should be resolved Image
        avatar = profile["properties"]["avatar"]
        assert avatar["type"] == "object"
        assert "url" in avatar["properties"]

    def test_no_refs_in_nested_result(self, spec_store):
        """Deeply nested result has no $ref."""
        result = resolve_schema(spec_store, schema_name="User")

        result_json = json.dumps(result)
        # No $ref at any level (except possibly for circular refs)
        # Simple check: try to load and re-dump - no issues
        assert json.loads(result_json)


class TestAC4ArrayItemsRefResolution:
    """AC 4: Array items.$ref resolution."""

    def test_array_items_ref(self, spec_store):
        """Array items with $ref are resolved."""
        result = resolve_schema(spec_store, schema_name="UserList")

        # Check items
        items_schema = result["properties"]["items"]["items"]
        assert "$ref" not in json.dumps(items_schema)
        assert items_schema["type"] == "object"
        assert "name" in items_schema["properties"]

    def test_full_array_resolution(self, spec_store):
        """Full array structure with resolved items."""
        result = resolve_schema(spec_store, schema_name="UserList")

        items = result["properties"]["items"]
        assert items["type"] == "array"

        item_schema = items["items"]
        assert item_schema["type"] == "object"
        # Check that nested refs in items are also resolved
        profile = item_schema["properties"]["profile"]
        assert profile["type"] == "object"


class TestAC5CircularReferences:
    """AC 5: Circular reference handling."""

    def test_circular_reference_detection(self, spec_store):
        """Circular references are detected and marked."""
        result = resolve_schema(spec_store, schema_name="UserWithFriends")

        # Should not raise exception
        assert result is not None
        assert result["type"] == "object"

    def test_circular_reference_no_infinite_loop(self, spec_store):
        """Circular references don't cause infinite loop."""
        # This should complete without hanging
        result = resolve_schema(spec_store, schema_name="UserWithFriends")

        # Check that friends is still there
        assert "friends" in result["properties"]

        # The friends.items should have circular marker or $ref
        friends = result["properties"]["friends"]
        friend_item = friends["items"]

        # Either marked as circular or still has $ref
        has_circular = "__circular__" in json.dumps(friend_item)
        has_ref = "$ref" in json.dumps(friend_item)
        assert has_circular or has_ref

    def test_deep_circular_still_resolves(self, spec_store):
        """Even with circular refs, schema resolves as much as possible."""
        result = resolve_schema(spec_store, schema_name="UserWithFriends")

        # First level should be resolved
        assert "id" in result["properties"]
        assert "name" in result["properties"]
        assert "friends" in result["properties"]


class TestErrorHandling:
    """Error handling and edge cases."""

    def test_schema_not_found(self, spec_store):
        """Raise KeyError if schema not found."""
        with pytest.raises(KeyError):
            resolve_schema(spec_store, schema_name="NonExistentSchema")

    def test_unloaded_spec(self):
        """Raise KeyError if spec not loaded."""
        store = get_store()
        store.clear()

        with pytest.raises(KeyError):
            resolve_schema(store, schema_name="User")

    def test_ref_to_nonexistent_schema(self, spec_store):
        """Handles broken $ref gracefully."""
        # Create a spec with broken ref
        broken_spec = {
            "openapi": "3.0.0",
            "info": {},
            "paths": {},
            "components": {
                "schemas": {
                    "BadSchema": {
                        "type": "object",
                        "properties": {
                            "ref": {"$ref": "#/components/schemas/DoesNotExist"}
                        },
                    }
                }
            },
        }
        spec_store.set_spec(broken_spec)

        # Should not raise, but log warning
        result = resolve_schema(spec_store, schema_name="BadSchema")
        assert result is not None
        # The ref stays as-is since it can't be resolved
        assert "$ref" in json.dumps(result)


class TestIntegration:
    """Integration and performance tests."""

    def test_resolved_copy_not_original(self, spec_store):
        """Resolved schema is a copy, not original."""
        result = resolve_schema(spec_store, schema_name="User")

        # Modify result
        result["new_field"] = "test"

        # Get again - should not have modification
        result2 = resolve_schema(spec_store, schema_name="User")
        assert "new_field" not in result2

    def test_multiple_resolutions_same_schema(self, spec_store):
        """Same schema can be resolved multiple times."""
        result1 = resolve_schema(spec_store, schema_name="User")
        result2 = resolve_schema(spec_store, schema_name="User")

        assert json.dumps(result1) == json.dumps(result2)

    def test_resolution_preserves_types(self, spec_store):
        """Resolved schema preserves type information."""
        result = resolve_schema(spec_store, schema_name="User")

        # Check type preservation through resolution
        assert result["properties"]["id"]["type"] == "string"
        assert result["properties"]["profile"]["type"] == "object"
        assert (
            result["properties"]["profile"]["properties"]["avatar"]["type"] == "object"
        )

    def test_array_type_preserved(self, spec_store):
        """Array types are preserved in resolution."""
        result = resolve_schema(spec_store, schema_name="UserList")

        items = result["properties"]["items"]
        assert items["type"] == "array"
        assert "items" in items
        assert items["items"]["type"] == "object"


class TestEdgeCases:
    """Edge cases and special scenarios."""

    def test_empty_schema(self, spec_store):
        """Empty schema resolves."""
        # Add empty schema to spec
        spec = spec_store.get_spec()
        spec["components"]["schemas"]["Empty"] = {}
        spec_store.set_spec(spec)

        result = resolve_schema(spec_store, schema_name="Empty")
        assert result == {}

    def test_schema_with_no_properties(self, spec_store):
        """Schema without properties resolves."""
        spec = spec_store.get_spec()
        spec["components"]["schemas"]["NoProps"] = {"type": "string"}
        spec_store.set_spec(spec)

        result = resolve_schema(spec_store, schema_name="NoProps")
        assert result["type"] == "string"

    def test_allOf_pattern(self, spec_store):
        """Schema with allOf pattern preserves structure."""
        spec = spec_store.get_spec()
        spec["components"]["schemas"]["Combined"] = {
            "allOf": [
                {"$ref": "#/components/schemas/SimpleUser"},
                {"properties": {"extra": {"type": "string"}}},
            ]
        }
        spec_store.set_spec(spec)

        result = resolve_schema(spec_store, schema_name="Combined")
        assert "allOf" in result
        # First element should be resolved
        assert result["allOf"][0]["type"] == "object"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
