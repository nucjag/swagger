"""
Tests for getAuthInfo tool (S11).

Tests extraction and parsing of authentication requirements from OpenAPI spec.
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.auth import get_auth_info
from core.spec_store import get_store


# Sample spec with various auth schemes
SAMPLE_SPEC_WITH_AUTH = {
    "openapi": "3.0.0",
    "info": {"title": "Test API", "version": "1.0.0"},
    "security": [{"api_key": []}, {"bearer": []}],
    "paths": {
        "/users": {
            "get": {
                "operationId": "listUsers",
                "security": [{"bearer": ["read:users"]}],
            }
        },
        "/public": {
            "get": {
                "operationId": "publicEndpoint",
                "security": [],
            }
        },
    },
    "components": {
        "securitySchemes": {
            "api_key": {
                "type": "apiKey",
                "in": "header",
                "name": "X-API-Key",
                "description": "API key in header",
            },
            "bearer": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
                "description": "Bearer token authentication",
            },
            "oauth2": {
                "type": "oauth2",
                "description": "OAuth2 authentication",
                "flows": {
                    "authorizationCode": {
                        "authorizationUrl": "https://example.com/oauth/authorize",
                        "tokenUrl": "https://example.com/oauth/token",
                        "refreshUrl": "https://example.com/oauth/refresh",
                        "scopes": {
                            "read:users": "Read user data",
                            "write:users": "Write user data",
                        },
                    },
                    "implicit": {
                        "authorizationUrl": "https://example.com/oauth/authorize",
                        "scopes": {
                            "read:posts": "Read posts",
                        },
                    },
                },
            },
            "basic": {
                "type": "http",
                "scheme": "basic",
                "description": "Basic authentication",
            },
        }
    },
}

SAMPLE_SPEC_NO_AUTH = {
    "openapi": "3.0.0",
    "info": {"title": "Public API", "version": "1.0.0"},
    "paths": {
        "/status": {"get": {"operationId": "status"}},
    },
    "components": {"securitySchemes": {}},
}


class TestGetAuthInfo:
    """Test getAuthInfo tool."""

    @pytest.fixture(autouse=True)
    def setup_spec(self):
        """Setup spec before each test."""
        store = get_store()
        store.set_spec(SAMPLE_SPEC_WITH_AUTH)

    def test_return_structure(self):
        """AC 1: Return proper structure with required fields."""
        result = get_auth_info()

        assert isinstance(result, dict)
        assert "required" in result
        assert "global" in result
        assert "schemes" in result
        assert "endpoints" in result

        assert isinstance(result["required"], bool)
        assert isinstance(result["global"], dict)
        assert isinstance(result["schemes"], list)
        assert isinstance(result["endpoints"], dict)

    def test_global_security_requirements(self):
        """AC 2: Extract global security requirements."""
        result = get_auth_info()

        assert result["global"]["required"] is True
        assert "api_key" in result["global"]["schemes"]
        assert "bearer" in result["global"]["schemes"]

    def test_security_schemes_parsing(self):
        """AC 1: Parse security schemes with types."""
        result = get_auth_info()

        scheme_names = {s["name"] for s in result["schemes"]}
        assert "api_key" in scheme_names
        assert "bearer" in scheme_names
        assert "oauth2" in scheme_names
        assert "basic" in scheme_names

    def test_api_key_scheme(self):
        """AC 6: Extract API Key scheme details."""
        result = get_auth_info()

        api_key_scheme = next(s for s in result["schemes"] if s["name"] == "api_key")
        assert api_key_scheme["type"] == "apiKey"
        assert api_key_scheme["in"] == "header"
        assert api_key_scheme["paramName"] == "X-API-Key"

    def test_bearer_token_format(self):
        """AC 5: Extract Bearer token format."""
        result = get_auth_info()

        bearer_scheme = next(s for s in result["schemes"] if s["name"] == "bearer")
        assert bearer_scheme["type"] == "http"
        assert bearer_scheme["scheme"] == "bearer"
        assert bearer_scheme["bearerFormat"] == "JWT"

    def test_oauth2_scopes(self):
        """AC 4: Extract OAuth2 scopes."""
        result = get_auth_info()

        oauth2_scheme = next(s for s in result["schemes"] if s["name"] == "oauth2")
        assert "scopes" in oauth2_scheme
        assert "read:users" in oauth2_scheme["scopes"]
        assert "write:users" in oauth2_scheme["scopes"]
        assert "read:posts" in oauth2_scheme["scopes"]

    def test_basic_auth_scheme(self):
        """Test HTTP Basic auth scheme."""
        result = get_auth_info()

        basic_scheme = next(s for s in result["schemes"] if s["name"] == "basic")
        assert basic_scheme["type"] == "http"
        assert basic_scheme["scheme"] == "basic"

    def test_per_endpoint_security_overrides(self):
        """AC 3: Detect per-endpoint security overrides."""
        result = get_auth_info()

        assert "/users" in result["endpoints"]
        assert result["endpoints"]["/users"]["overrides"] is True
        assert result["endpoints"]["/users"]["required"] is True
        assert "bearer" in result["endpoints"]["/users"]["schemes"]

    def test_no_auth_endpoint(self):
        """AC 8: Handle endpoint with no auth required."""
        result = get_auth_info()

        assert "/public" in result["endpoints"]
        assert result["endpoints"]["/public"]["overrides"] is True
        assert result["endpoints"]["/public"]["required"] is False
        assert result["endpoints"]["/public"]["schemes"] == []

    def test_no_sensitive_data(self):
        """AC 7: Ensure no sensitive credentials in response."""
        result = get_auth_info()

        # Convert to string to search for any obvious secrets
        result_str = str(result)
        assert "secret" not in result_str.lower()
        assert "password" not in result_str.lower()
        assert "token" not in result_str.lower() or "tokenUrl" in result_str

    def test_oauth2_flows(self):
        """Test OAuth2 flows parsing."""
        result = get_auth_info()

        oauth2_scheme = next(s for s in result["schemes"] if s["name"] == "oauth2")
        assert "flows" in oauth2_scheme
        assert "authorizationCode" in oauth2_scheme["flows"]
        assert "implicit" in oauth2_scheme["flows"]

        auth_code_flow = oauth2_scheme["flows"]["authorizationCode"]
        assert auth_code_flow["authorizationUrl"] is not None
        assert auth_code_flow["tokenUrl"] is not None
        assert auth_code_flow["refreshUrl"] is not None


class TestGetAuthInfoNoAuth:
    """Test getAuthInfo with spec without auth."""

    @pytest.fixture(autouse=True)
    def setup_spec(self):
        """Setup spec without auth."""
        store = get_store()
        store.set_spec(SAMPLE_SPEC_NO_AUTH)

    def test_no_auth_required(self):
        """AC 8: Return no auth required for public API."""
        result = get_auth_info()

        assert result["required"] is False
        assert result["global"]["required"] is False
        assert result["schemes"] == []
        assert result["endpoints"] == {}

    def test_empty_schemes_list(self):
        """Test empty schemes list."""
        result = get_auth_info()

        assert isinstance(result["schemes"], list)
        assert len(result["schemes"]) == 0


class TestGetAuthInfoEdgeCases:
    """Test edge cases."""

    def test_empty_spec(self):
        """Test with minimal/empty spec."""
        store = get_store()
        store.set_spec({})

        result = get_auth_info()

        assert result["required"] is False
        assert result["schemes"] == []

    def test_scheme_with_description(self):
        """Test that scheme descriptions are preserved."""
        spec = {
            "openapi": "3.0.0",
            "components": {
                "securitySchemes": {
                    "api_key": {
                        "type": "apiKey",
                        "in": "header",
                        "name": "X-API-Key",
                        "description": "Our API key",
                    }
                }
            },
            "paths": {},
        }

        store = get_store()
        store.set_spec(spec)

        result = get_auth_info()

        scheme = result["schemes"][0]
        assert "description" in scheme
        assert scheme["description"] == "Our API key"

    def test_api_key_in_query(self):
        """Test API Key in query parameter."""
        spec = {
            "openapi": "3.0.0",
            "components": {
                "securitySchemes": {
                    "query_key": {
                        "type": "apiKey",
                        "in": "query",
                        "name": "api_token",
                    }
                }
            },
            "paths": {},
        }

        store = get_store()
        store.set_spec(spec)

        result = get_auth_info()

        scheme = result["schemes"][0]
        assert scheme["in"] == "query"
        assert scheme["paramName"] == "api_token"

    def test_api_key_in_cookie(self):
        """Test API Key in cookie."""
        spec = {
            "openapi": "3.0.0",
            "components": {
                "securitySchemes": {
                    "cookie_key": {
                        "type": "apiKey",
                        "in": "cookie",
                        "name": "auth_token",
                    }
                }
            },
            "paths": {},
        }

        store = get_store()
        store.set_spec(spec)

        result = get_auth_info()

        scheme = result["schemes"][0]
        assert scheme["in"] == "cookie"
        assert scheme["paramName"] == "auth_token"

    def test_multiple_global_schemes(self):
        """Test multiple global security schemes."""
        spec = {
            "openapi": "3.0.0",
            "security": [
                {"api_key": []},
                {"oauth2": ["read:all"]},
            ],
            "components": {
                "securitySchemes": {
                    "api_key": {"type": "apiKey", "in": "header", "name": "X-API-Key"},
                    "oauth2": {"type": "oauth2", "flows": {}},
                }
            },
            "paths": {},
        }

        store = get_store()
        store.set_spec(spec)

        result = get_auth_info()

        assert result["global"]["required"] is True
        assert "api_key" in result["global"]["schemes"]
        assert "oauth2" in result["global"]["schemes"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
