"""
Request validation against endpoint contract.

Implements: validateRequest (S10)
"""

from typing import Dict, Any, List, Optional


def validate_request(path: str, method: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate request data against endpoint contract.

    Args:
        path: API path (e.g., "/users/{id}")
        method: HTTP method (GET, POST, PUT, DELETE, etc.)
        data: Request data to validate (typically requestBody)

    Returns:
        {
            "valid": bool,
            "errors": [
                {
                    "path": "field.name[0]",
                    "message": "error description"
                }
            ]
        }
    """
    from core.spec_store import get_store
    from tools.contract import get_endpoint_contract
    from tools.schema_resolver import resolve_schema

    spec_store = get_store()
    errors = []

    try:
        # Get endpoint contract
        contract = get_endpoint_contract(spec_store, path=path, method=method)

        # Extract requestBody schema
        request_body = contract.get("requestBody")
        if not request_body:
            # No requestBody expected
            return {"valid": True, "errors": []}

        # Get the schema from content
        content = request_body.get("content", {})
        content_type = list(content.keys())[0] if content else "application/json"
        schema = content.get(content_type, {}).get("schema", {})

        if not schema:
            return {"valid": True, "errors": []}

        # Resolve schema (expand $ref)
        if "$ref" in schema:
            schema_name = schema["$ref"].split("/")[-1]
            schema = resolve_schema(spec_store, schema_name=schema_name)

        # Validate data against schema
        validation_errors = _validate_against_schema(schema, data, root_path="")

        if validation_errors:
            return {"valid": False, "errors": validation_errors}
        else:
            return {"valid": True, "errors": []}

    except Exception as e:
        return {
            "valid": False,
            "errors": [{"path": "", "message": f"Validation error: {str(e)}"}],
        }


def _validate_against_schema(
    schema: Dict[str, Any], data: Any, root_path: str = ""
) -> List[Dict[str, str]]:
    """
    Recursively validate data against JSON schema.

    Args:
        schema: JSON Schema definition
        data: Data to validate
        root_path: Current path in the data structure (for error reporting)

    Returns:
        List of validation errors
    """
    errors = []

    if not schema:
        return errors

    schema_type = schema.get("type")

    # Handle $ref (should be already resolved, but just in case)
    if "$ref" in schema:
        from tools.schema_resolver import resolve_schema
        from core.spec_store import get_store

        spec_store = get_store()
        schema_name = schema["$ref"].split("/")[-1]
        resolved_schema = resolve_schema(spec_store, schema_name=schema_name)
        return _validate_against_schema(resolved_schema, data, root_path)

    # Type validation
    if schema_type:
        type_errors = _validate_type(schema_type, data, root_path)
        errors.extend(type_errors)

        if type_errors:  # If type is wrong, don't continue validation
            return errors

    # Type-specific validations
    if schema_type == "object":
        errors.extend(_validate_object(schema, data, root_path))
    elif schema_type == "array":
        errors.extend(_validate_array(schema, data, root_path))
    elif schema_type == "string":
        errors.extend(_validate_string(schema, data, root_path))
    elif schema_type in ("integer", "number"):
        errors.extend(_validate_numeric(schema, data, root_path, schema_type))

    # Enum validation (works for any type)
    if "enum" in schema:
        if data not in schema["enum"]:
            allowed = ", ".join(str(e) for e in schema["enum"])
            errors.append(
                {
                    "path": root_path or "root",
                    "message": f"invalid enum value: {data}, allowed: {allowed}",
                }
            )

    return errors


def _validate_type(schema_type: str, data: Any, root_path: str) -> List[Dict[str, str]]:
    """Validate data type matches schema type."""
    errors = []

    type_mapping = {
        "null": type(None),
        "boolean": bool,
        "object": dict,
        "array": list,
        "number": (int, float),
        "integer": int,
        "string": str,
    }

    expected_type = type_mapping.get(schema_type)
    if expected_type and not isinstance(data, expected_type):
        # Special case: integer should accept int but not float with decimals
        if schema_type == "integer" and isinstance(data, float):
            if data != int(data):
                errors.append(
                    {
                        "path": root_path or "root",
                        "message": f"expected {schema_type}, got {type(data).__name__}",
                    }
                )
        elif schema_type == "integer" and isinstance(data, str):
            # Try to parse string as integer
            try:
                int(data)
            except ValueError:
                errors.append(
                    {
                        "path": root_path or "root",
                        "message": f"expected {schema_type}, got {type(data).__name__}",
                    }
                )
        else:
            errors.append(
                {
                    "path": root_path or "root",
                    "message": f"expected {schema_type}, got {type(data).__name__}",
                }
            )

    return errors


def _validate_object(
    schema: Dict[str, Any], data: Dict[str, Any], root_path: str
) -> List[Dict[str, str]]:
    """Validate object properties."""
    errors = []

    if not isinstance(data, dict):
        return errors  # Type error already reported

    properties = schema.get("properties", {})
    required = schema.get("required", [])

    # Check required fields
    for field_name in required:
        if field_name not in data:
            field_path = f"{root_path}.{field_name}" if root_path else field_name
            errors.append(
                {
                    "path": field_path,
                    "message": "required field missing",
                }
            )

    # Validate each property
    for field_name, field_value in data.items():
        if field_name in properties:
            field_path = f"{root_path}.{field_name}" if root_path else field_name
            field_schema = properties[field_name]
            field_errors = _validate_against_schema(field_schema, field_value, field_path)
            errors.extend(field_errors)

    return errors


def _validate_array(
    schema: Dict[str, Any], data: List[Any], root_path: str
) -> List[Dict[str, str]]:
    """Validate array items."""
    errors = []

    if not isinstance(data, list):
        return errors  # Type error already reported

    item_schema = schema.get("items", {})
    min_items = schema.get("minItems")
    max_items = schema.get("maxItems")

    # Check array length
    if min_items is not None and len(data) < min_items:
        errors.append(
            {
                "path": root_path or "root",
                "message": f"minimum items {min_items}, got {len(data)}",
            }
        )

    if max_items is not None and len(data) > max_items:
        errors.append(
            {
                "path": root_path or "root",
                "message": f"maximum items {max_items}, got {len(data)}",
            }
        )

    # Validate each item
    for idx, item in enumerate(data):
        item_path = f"{root_path}[{idx}]" if root_path else f"[{idx}]"
        item_errors = _validate_against_schema(item_schema, item, item_path)
        errors.extend(item_errors)

    return errors


def _validate_string(
    schema: Dict[str, Any], data: str, root_path: str
) -> List[Dict[str, str]]:
    """Validate string properties."""
    errors = []

    if not isinstance(data, str):
        return errors  # Type error already reported

    min_length = schema.get("minLength")
    max_length = schema.get("maxLength")
    pattern = schema.get("pattern")

    # Check length
    if min_length is not None and len(data) < min_length:
        errors.append(
            {
                "path": root_path or "root",
                "message": f"minimum length {min_length}, got {len(data)}",
            }
        )

    if max_length is not None and len(data) > max_length:
        errors.append(
            {
                "path": root_path or "root",
                "message": f"maximum length {max_length}, got {len(data)}",
            }
        )

    # Check pattern (basic regex)
    if pattern:
        import re

        try:
            if not re.match(pattern, data):
                errors.append(
                    {
                        "path": root_path or "root",
                        "message": f"does not match pattern: {pattern}",
                    }
                )
        except re.error:
            # Invalid regex pattern - skip
            pass

    return errors


def _validate_numeric(
    schema: Dict[str, Any],
    data: Any,
    root_path: str,
    schema_type: str,
) -> List[Dict[str, str]]:
    """Validate numeric properties."""
    errors = []

    if not isinstance(data, (int, float)):
        return errors  # Type error already reported

    minimum = schema.get("minimum")
    maximum = schema.get("maximum")
    exclusive_minimum = schema.get("exclusiveMinimum")
    exclusive_maximum = schema.get("exclusiveMaximum")

    # Check bounds
    if minimum is not None and data < minimum:
        errors.append(
            {
                "path": root_path or "root",
                "message": f"minimum {minimum}, got {data}",
            }
        )

    if maximum is not None and data > maximum:
        errors.append(
            {
                "path": root_path or "root",
                "message": f"maximum {maximum}, got {data}",
            }
        )

    if exclusive_minimum is not None and data <= exclusive_minimum:
        errors.append(
            {
                "path": root_path or "root",
                "message": f"exclusive minimum {exclusive_minimum}, got {data}",
            }
        )

    if exclusive_maximum is not None and data >= exclusive_maximum:
        errors.append(
            {
                "path": root_path or "root",
                "message": f"exclusive maximum {exclusive_maximum}, got {data}",
            }
        )

    return errors
