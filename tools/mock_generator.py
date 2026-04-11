"""
Mock data generation from schemas.

Implements: generateMockData (S9)
"""

from typing import Dict, Any


def generate_mock_data(schema_name: str, count: int = 1) -> Dict[str, Any]:
    """
    Generate realistic mock data for a schema.

    Args:
        schema_name: Schema name or $ref to generate mocks for
        count: Number of mock instances to generate

    Returns:
        dict: {"success": true, "data": [objects]}
    """
    from core.spec_store import get_store
    from tools.schema_resolver import resolve_schema

    spec_store = get_store()

    try:
        # Resolve schema to get full definition (expands $ref)
        resolved_schema = resolve_schema(spec_store, schema_name)

        # Generate count mock objects
        mock_objects = []
        for i in range(count):
            # For first object, use examples if available
            use_examples = i == 0
            mock_obj = _generate_from_schema(
                resolved_schema, use_examples=use_examples, counter=i
            )
            mock_objects.append(mock_obj)

        return {"success": True, "data": mock_objects}
    except KeyError as e:
        return {"success": False, "error": f"Schema not found: {str(e)}"}
    except Exception as e:
        return {"success": False, "error": f"Failed to generate mock data: {str(e)}"}


def _generate_from_schema(
    schema: Dict[str, Any], use_examples: bool = False, counter: int = 0, depth: int = 0
) -> Any:
    """
    Recursively generate mock value from schema (without external dependencies).

    Args:
        schema: JSON Schema definition
        use_examples: Whether to prioritize examples/defaults
        counter: Counter for unique value generation
        depth: Recursion depth (prevent infinite loops)

    Returns:
        Generated mock value
    """
    import random
    import uuid as uuid_lib
    from datetime import datetime, timedelta

    if depth > 20:  # Prevent deep recursion
        return None

    # Handle example/default priority (defaults always, examples only for first object)
    if "example" in schema and use_examples:
        return schema["example"]
    if "default" in schema:
        return schema["default"]

    schema_type = schema.get("type", "string")

    # Handle $ref (circular detection)
    if "__circular__" in schema:
        return None

    if schema_type == "object":
        obj = {}
        properties = schema.get("properties", {})
        required = schema.get("required", [])

        for prop_name, prop_schema in properties.items():
            if prop_name in required or True:  # Generate all properties
                obj[prop_name] = _generate_from_schema(
                    prop_schema,
                    use_examples=use_examples,
                    counter=counter,
                    depth=depth + 1,
                )

        return obj

    elif schema_type == "array":
        item_schema = schema.get("items", {"type": "string"})
        min_items = schema.get("minItems", 1)
        max_items = schema.get("maxItems", 3)
        count = random.randint(min_items, max_items)

        return [
            _generate_from_schema(item_schema, counter=counter + i, depth=depth + 1)
            for i in range(count)
        ]

    elif schema_type == "string":
        # Check format for specific string types
        schema_format = schema.get("format", "")

        if schema_format == "email":
            return f"user{counter}@example.com"
        elif schema_format == "uri" or schema_format == "url":
            return f"https://example.com/resource/{counter}"
        elif schema_format == "uuid":
            return str(uuid_lib.UUID(int=counter + 1))
        elif schema_format == "date":
            date = datetime.now() + timedelta(days=counter)
            return date.strftime("%Y-%m-%d")
        elif schema_format == "date-time":
            date = datetime.now() + timedelta(days=counter)
            return date.isoformat()
        elif schema_format == "time":
            return f"{counter % 24:02d}:{(counter * 5) % 60:02d}:00"
        elif "enum" in schema:
            return schema["enum"][counter % len(schema["enum"])]
        else:
            # Generic string
            pattern = schema.get("pattern", None)
            max_length = schema.get("maxLength", 20)

            if pattern:
                # Simple pattern handling - just generate alphanumeric
                return "SAMPLE"[:max_length]
            else:
                words = [
                    "sample",
                    "test",
                    "mock",
                    "data",
                    "value",
                    "item",
                    "object",
                    "string",
                ]
                base = words[counter % len(words)]
                if counter > 0:
                    base += str(counter)
                return base[:max_length]

    elif schema_type == "integer":
        minimum = schema.get("minimum", 0)
        maximum = schema.get("maximum", 100)
        return minimum + (counter % max(1, (maximum - minimum + 1)))

    elif schema_type == "number":
        minimum = schema.get("minimum", 0.0)
        maximum = schema.get("maximum", 100.0)
        value = minimum + ((counter % 10) / 10.0) * (maximum - minimum)
        return round(value, 2)

    elif schema_type == "boolean":
        return counter % 2 == 0

    elif "enum" in schema:
        return schema["enum"][counter % len(schema["enum"])]

    else:
        return None
