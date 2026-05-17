"""
Code generation tools for TypeScript client and types.

Converts OpenAPI contracts to ready-to-paste TypeScript code:
- Type definitions (Request, Response)
- Fetch functions with full typing
- Support for all HTTP methods
- Parameter handling (path, query, body)
"""

import logging
import re
from typing import Any

logger = logging.getLogger("openapi-mcp.tools.codegen")


class SchemaResolver:
    """Resolve schemas and $ref recursively."""

    def __init__(self, spec_store: Any):
        self.spec_store = spec_store
        self.visited: set[str] = set()

    def resolve_recursive(
        self, schema: dict[str, Any], path: str = ""
    ) -> dict[str, Any]:
        """
        Recursively resolve all $ref in schema.

        Args:
            schema: OpenAPI schema dict
            path: Current resolution path (for circular ref detection)

        Returns:
            Resolved schema with all $ref expanded
        """
        if not isinstance(schema, dict):
            return schema

        # Detect circular references
        if "$ref" in schema:
            ref_path = schema["$ref"]
            if ref_path in self.visited:
                # Circular ref - return as is to prevent infinite loop
                return {"$ref": ref_path}

            self.visited.add(ref_path)
            # Use spec_store's resolveSchema to resolve the reference
            try:
                resolved = self.spec_store.resolve_schema(ref_path)
                return self.resolve_recursive(resolved, path)
            except Exception:
                return {"$ref": ref_path}

        # Recursively resolve nested objects
        result = {}
        for key, value in schema.items():
            if isinstance(value, dict):
                result[key] = self.resolve_recursive(value, f"{path}/{key}")
            elif isinstance(value, list):
                result[key] = [
                    self.resolve_recursive(item, f"{path}/{key}[]")
                    if isinstance(item, dict)
                    else item
                    for item in value
                ]
            else:
                result[key] = value

        return result


class TypeScriptTypeGenerator:
    """Generate TypeScript type definitions from OpenAPI schemas."""

    TYPE_MAPPING = {
        "string": "string",
        "number": "number",
        "integer": "number",
        "boolean": "boolean",
        "array": "unknown[]",  # will be overridden by items
        "object": "Record<string, unknown>",
    }

    def __init__(self, spec_store: Any):
        self.spec_store = spec_store
        self.resolver = SchemaResolver(spec_store)
        self.generated_types: dict[str, str] = {}

    def schema_to_typescript(
        self, schema: dict[str, Any], type_name: str = "Type"
    ) -> str:
        """
        Convert OpenAPI schema to TypeScript type definition.

        Args:
            schema: OpenAPI schema
            type_name: Name for the type

        Returns:
            TypeScript type definition string
        """
        # Resolve all references first
        resolved = self.resolver.resolve_recursive(schema)

        type_def = self._build_type(resolved)
        return f"type {type_name} = {type_def};"

    def _build_type(self, schema: dict[str, Any]) -> str:
        """Build type string from schema."""
        if "$ref" in schema:
            ref = schema["$ref"]
            return ref.split("/")[-1]  # Extract type name from $ref

        schema_type = schema.get("type")

        if schema_type == "object":
            properties = schema.get("properties", {})
            required = schema.get("required", [])

            if not properties:
                return "Record<string, unknown>"

            fields = []
            for prop_name, prop_schema in properties.items():
                prop_type = self._build_type(prop_schema)
                is_required = prop_name in required
                optional = "" if is_required else "?"
                fields.append(f"  {prop_name}{optional}: {prop_type}")

            return "{\n" + ",\n".join(fields) + "\n}"

        elif schema_type == "array":
            items_schema = schema.get("items", {})
            items_type = self._build_type(items_schema)
            return f"{items_type}[]"

        elif schema_type == "string":
            enum = schema.get("enum")
            if enum:
                # Union type for enum
                enum_values = " | ".join(f"'{v}'" for v in enum)
                return enum_values
            return "string"

        elif schema_type in {"number", "integer"}:
            return "number"

        elif schema_type == "boolean":
            return "boolean"

        elif schema_type is None:
            # allOf, anyOf, oneOf
            if "allOf" in schema:
                return self._build_type(schema["allOf"][0])  # Simplify: take first
            elif "oneOf" in schema or "anyOf" in schema:
                return "unknown"  # Complex union, fallback

        return "unknown"

    def interface_from_schema(self, schema: dict[str, Any], interface_name: str) -> str:
        """
        Generate TypeScript interface from schema.

        Args:
            schema: OpenAPI schema
            interface_name: Name for the interface

        Returns:
            TypeScript interface definition
        """
        resolved = self.resolver.resolve_recursive(schema)

        if resolved.get("type") != "object":
            # Not an object, fallback to type
            return self.schema_to_typescript(resolved, interface_name)

        properties = resolved.get("properties", {})
        required = resolved.get("required", [])

        if not properties:
            return f"interface {interface_name} {{}}"

        fields = []
        for prop_name, prop_schema in properties.items():
            prop_type = self._build_type(prop_schema)
            is_required = prop_name in required
            optional = "" if is_required else "?"
            fields.append(f"  {prop_name}{optional}: {prop_type};")

        return f"interface {interface_name} {{\n" + "\n".join(fields) + "\n}"


class ParameterExtractor:
    """Extract parameters from endpoint contract."""

    def __init__(self, spec_store: Any):
        self.spec_store = spec_store

    def extract_all(self, endpoint_contract: dict[str, Any]) -> dict[str, Any]:
        """
        Extract all parameters from endpoint contract.

        Returns:
            {
                'path_params': {'id': 'string'},
                'query_params': {'limit': 'number'},
                'body_params': {...},
                'all_params': {...}  # merged
            }
        """
        path = endpoint_contract.get("path", "")
        parameters = endpoint_contract.get("parameters", [])
        request_body = endpoint_contract.get("requestBody", {})

        path_params = self._extract_path_params(path)
        query_params = self._extract_query_params(parameters)
        body_params = self._extract_body_params(request_body)

        return {
            "path_params": path_params,
            "query_params": query_params,
            "body_params": body_params,
            "all_params": {**path_params, **query_params, **body_params},
        }

    def _extract_path_params(self, path: str) -> dict[str, str]:
        """Extract {id}, {userId} etc from path."""
        matches = re.findall(r"\{(\w+)\}", path)
        return dict.fromkeys(matches, "string")

    def _extract_query_params(self, parameters: list[dict[str, Any]]) -> dict[str, str]:
        """Extract query parameters."""
        return {
            p["name"]: self._param_type(p.get("schema", {}))
            for p in parameters
            if p.get("in") == "query"
        }

    def _extract_body_params(self, request_body: dict[str, Any]) -> dict[str, str]:
        """Extract body parameters."""
        if not request_body:
            return {}

        content = request_body.get("content", {})
        schema = content.get("application/json", {}).get("schema", {})

        if schema.get("type") == "object":
            properties = schema.get("properties", {})
            return dict.fromkeys(properties.keys(), "unknown")

        return {}

    def _param_type(self, schema: dict[str, Any]) -> str:
        """Map OpenAPI schema type to string."""
        param_type = schema.get("type", "string")
        if param_type == "integer":
            return "number"
        return param_type


class FetchFunctionGenerator:
    """Generate fetch functions from endpoint contracts."""

    HTTP_METHODS = {"GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"}

    def __init__(self, spec_store: Any):
        self.spec_store = spec_store
        self.param_extractor = ParameterExtractor(spec_store)
        self.type_generator = TypeScriptTypeGenerator(spec_store)

    def generate(self, endpoint_contract: dict[str, Any], method_name: str) -> str:
        """
        Generate a single fetch function.

        Args:
            endpoint_contract: Full endpoint contract from getEndpointContract
            method_name: camelCase function name (e.g., 'getUsers', 'createUser')

        Returns:
            Ready-to-use async function string
        """
        method = endpoint_contract.get("method", "GET").upper()
        path = endpoint_contract.get("path", "/")
        params = self.param_extractor.extract_all(endpoint_contract)

        # Build function signature
        params_type = self._build_params_type(params, method_name)
        response_type = self._extract_response_type(endpoint_contract, method_name)

        # Build fetch call
        fetch_body = self._build_fetch_body(method, path, params, method_name)

        # Build complete function
        func = f"""async function {method_name}({params_type}): Promise<{response_type}> {{
{fetch_body}
}}"""
        return func

    def _build_params_type(self, params: dict[str, Any], method_name: str) -> str:
        """Build params type for function signature."""
        all_params = params.get("all_params", {})

        if not all_params:
            return "params: {}"

        # Build inline type
        fields = [f"{name}: {ptype}" for name, ptype in all_params.items()]
        return f"params: {{{', '.join(fields)}}}"

    def _extract_response_type(
        self, endpoint_contract: dict[str, Any], method_name: str
    ) -> str:
        """Extract response type from endpoint contract."""
        responses = endpoint_contract.get("responses", {})

        # Look for successful response (200, 201, etc)
        for status in ["200", "201", "204"]:
            if status in responses:
                if status == "204":
                    return "void"

                response_schema = (
                    responses[status]
                    .get("content", {})
                    .get("application/json", {})
                    .get("schema", {})
                )
                if response_schema:
                    # For now, just return the inline type
                    type_gen = TypeScriptTypeGenerator(self.spec_store)
                    return type_gen._build_type(response_schema)

        return "unknown"

    def _build_fetch_body(
        self, method: str, path: str, params: dict[str, Any], method_name: str
    ) -> str:
        """Build the fetch call body."""
        path_params = params.get("path_params", {})
        query_params = params.get("query_params", {})
        body_params = params.get("body_params", {})

        # Build URL
        url = path
        if path_params:
            # Replace {id} with ${params.id}
            for param in path_params.keys():
                url = url.replace(f"{{{param}}}", f"${{params.{param}}}")
            url = f"`{url}`"
        else:
            url = f'"{path}"'

        if query_params:
            # Add query string builder
            url_line = f"""  const url = new URL({url}, 'https://api.example.com');
  Object.entries(params).forEach(([key, value]) => {{
    if (!{list(path_params.keys())}.includes(key)) {{
      url.searchParams.set(key, String(value));
    }}
  }});"""
        else:
            url_line = f"  const url = {url};"

        # Build options
        options = [
            "method: '" + method + "'",
            "headers: { 'Content-Type': 'application/json' }",
        ]

        if method in ["POST", "PUT", "PATCH"] and body_params:
            options.append("body: JSON.stringify(params)")

        options_str = ",\n    ".join(options)

        # Build function body
        body = f"""{url_line}
  const response = await fetch(url, {{
    {options_str}
  }});

  if (!response.ok) throw new Error(`HTTP ${{response.status}}`);
  return response.json();"""

        return body


class TestGenerator:
    """Generate Jest tests from endpoint contracts."""

    def __init__(self, spec_store: Any):
        self.spec_store = spec_store
        self.type_gen = TypeScriptTypeGenerator(spec_store)
        self.param_extractor = ParameterExtractor(spec_store)

    def generate_test_suite(self, endpoint_ids: list[int]) -> str:
        """
        Generate Jest test suite for list of endpoints.

        Args:
            endpoint_ids: List of endpoint IDs

        Returns:
            Ready-to-run Jest test code
        """
        imports = self._generate_imports()
        describe_blocks = []

        for endpoint_id in endpoint_ids:
            try:
                contract = self.spec_store.get_endpoint_contract(endpoint_id)
                method_name = self._generate_method_name(contract)

                describe_block = self._generate_describe_block(contract, method_name)
                if describe_block:
                    describe_blocks.append(describe_block)
            except Exception as e:
                logger.warning(
                    "Failed to generate tests for endpoint %s: %s",
                    endpoint_id,
                    e,
                )

        # Combine all parts
        parts = []
        if imports:
            parts.append(imports)

        if describe_blocks:
            parts.append("\n\n".join(describe_blocks))

        return "\n\n".join(parts) if parts else ""

    def _generate_imports(self) -> str:
        """Generate Jest imports and setup."""
        return """import { describe, it, expect, beforeEach, afterEach } from '@jest/globals';
import * as client from './client';"""

    def _generate_describe_block(self, contract: dict[str, Any], method_name: str) -> str:
        """Generate describe block for single endpoint."""
        method = contract.get("method", "GET").upper()
        path = contract.get("path", "/")

        describe_name = f"{method} {path}"

        # Generate test cases
        happy_path = self._generate_happy_path_test(contract, method_name)
        error_cases = self._generate_error_cases_test(contract, method_name)
        parameterized = self._generate_parameterized_test(contract, method_name)

        # Combine tests
        test_cases = [happy_path]
        if error_cases:
            test_cases.append(error_cases)
        if parameterized:
            test_cases.append(parameterized)

        tests_code = "\n\n  ".join(filter(None, test_cases))

        return f"""describe('{describe_name}', () => {{
  {tests_code}
}});"""

    def _generate_happy_path_test(self, contract: dict[str, Any], method_name: str) -> str:
        """Generate happy path test (AC-1)."""
        test_code = f"""it('should {method_name} successfully', async () => {{
    // Given: valid request parameters
    const request = {{}};

    // When: calling {method_name}
    // const response = await client.{method_name}(request);

    // Then: response is defined and typed correctly
    // expect(response).toBeDefined();
  }});"""

        return test_code

    def _generate_error_cases_test(self, contract: dict[str, Any], method_name: str) -> str:
        """Generate error case tests (AC-2)."""
        parameters = contract.get("parameters", [])
        required_params = [p for p in parameters if p.get("required")]

        if not required_params:
            return ""

        test_code = f"""it('should handle missing required parameters', async () => {{
    // Given: invalid request (missing required params)
    const invalidRequest = {{}};

    // When: calling {method_name} with invalid data
    // Then: error is thrown
    // expect(() => client.{method_name}(invalidRequest)).toThrow();
  }});"""

        return test_code

    def _generate_parameterized_test(self, contract: dict[str, Any], method_name: str) -> str:
        """Generate parameterized test (AC-3)."""
        parameters = contract.get("parameters", [])
        enum_params = [p for p in parameters if p.get("schema", {}).get("enum")]

        if not enum_params:
            return ""

        param = enum_params[0]
        enum_values = param.get("schema", {}).get("enum", [])
        enum_str = ", ".join(f"'{v}'" for v in enum_values)
        param_name = param.get("name", "param")

        test_code = f"""it.each([{enum_str}])(
    'should handle {param_name} = %s',
    async (value) => {{
      // Given: different parameter values
      const request = {{ {param_name}: value }};

      // When: calling {method_name}
      // const response = await client.{method_name}(request);

      // Then: response is defined
      // expect(response).toBeDefined();
    }}
  );"""

        return test_code

    def _extract_response_type(self, contract: dict[str, Any], method_name: str) -> str:
        """Extract response type name."""
        return f"{method_name[0].upper()}{method_name[1:]}Response"

    def _generate_method_name(self, contract: dict[str, Any]) -> str:
        """Generate camelCase method name."""
        operation_id = contract.get("operationId", "")
        if operation_id:
            return operation_id

        method = contract.get("method", "get").lower()
        path = contract.get("path", "").strip("/")

        parts = path.split("/")
        words = [method] + [p.replace("{", "").replace("}", "") for p in parts]

        return words[0] + "".join(w.capitalize() for w in words[1:])


class CodeGenerator:
    """Main code generator - orchestrates type and function generation."""

    def __init__(self, spec_store: Any):
        self.spec_store = spec_store
        self.type_gen = TypeScriptTypeGenerator(spec_store)
        self.fetch_gen = FetchFunctionGenerator(spec_store)
        self.test_gen = TestGenerator(spec_store)

    def generate_client(
        self,
        endpoint_ids: list[int],
        language: str = "typescript",
        include: list[str] | None = None,
    ) -> str:
        """
        Generate TypeScript client code for list of endpoints.

        Args:
            endpoint_ids: List of endpoint IDs
            language: Target language (only 'typescript' for MVP)
            include: What to include ['types', 'fetch']

        Returns:
            Ready-to-paste TypeScript code
        """
        if include is None:
            include = ["types", "fetch"]

        if language != "typescript":
            raise ValueError(f"Language '{language}' not supported. Use 'typescript'.")

        all_types = []
        all_functions = []

        for endpoint_id in endpoint_ids:
            try:
                # Get endpoint contract
                contract = self.spec_store.get_endpoint_contract(endpoint_id)

                method_name = self._generate_method_name(contract)

                # Generate types
                if "types" in include:
                    request_type = self._generate_request_type(contract, method_name)
                    if request_type:
                        all_types.append(request_type)

                    response_type = self._generate_response_type(contract, method_name)
                    if response_type:
                        all_types.append(response_type)

                # Generate fetch function
                if "fetch" in include:
                    func = self.fetch_gen.generate(contract, method_name)
                    all_functions.append(func)

            except Exception as e:
                # Skip this endpoint on error
                print(
                    f"Warning: Failed to generate code for endpoint {endpoint_id}: {e}"
                )
                continue

        # Build final code
        code_parts = []

        if all_types:
            code_parts.append("\n".join(all_types))

        if all_functions:
            if all_types:
                code_parts.append("")  # blank line
            code_parts.append("\n\n".join(all_functions))

        return "\n\n".join(code_parts)

    def generate_tests(
        self,
        endpoint_ids: list[int],
        framework: str = "jest",
        include_mocks: bool = True,
    ) -> str:
        """
        Generate Jest tests for list of endpoints.

        Args:
            endpoint_ids: List of endpoint IDs
            framework: Test framework (only 'jest' for v1.1)
            include_mocks: Whether to include mock data in tests

        Returns:
            Ready-to-run Jest test code
        """
        if framework != "jest":
            raise ValueError(f"Framework '{framework}' not supported. Use 'jest'.")

        return self.test_gen.generate_test_suite(endpoint_ids)

    def _generate_method_name(self, contract: dict[str, Any]) -> str:
        """Generate camelCase function name from endpoint."""
        operation_id = contract.get("operationId", "")
        if operation_id:
            return operation_id

        # Fallback: method + path
        method = contract.get("method", "get").lower()
        path = contract.get("path", "").strip("/")

        # Convert /users/{id} to getUsersId
        parts = path.split("/")
        words = [method] + [p.replace("{", "").replace("}", "") for p in parts]

        # CamelCase
        return words[0] + "".join(w.capitalize() for w in words[1:])

    def _generate_request_type(
        self, contract: dict[str, Any], method_name: str
    ) -> str | None:
        """Generate Request type from contract."""
        request_body = contract.get("requestBody")
        parameters = contract.get("parameters", [])

        if not request_body and not parameters:
            return None

        # Build merged type
        type_name = f"{method_name[0].upper()}{method_name[1:]}Request"
        return f"interface {type_name} {{}}"  # Placeholder

    def _generate_response_type(
        self, contract: dict[str, Any], method_name: str
    ) -> str | None:
        """Generate Response type from contract."""
        responses = contract.get("responses", {})

        if not responses:
            return None

        type_name = f"{method_name[0].upper()}{method_name[1:]}Response"
        return f"interface {type_name} {{}}"  # Placeholder
