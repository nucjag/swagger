"""
Tests for authenticatedDebugRequest tool (S12).
"""

from __future__ import annotations

from dataclasses import dataclass
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import tools.debug_request as debug_request
from core.spec_store import get_store


SAMPLE_SPEC = {
    "openapi": "3.0.0",
    "servers": [{"url": "https://api.example.com"}],
    "security": [{"bearer": []}],
    "paths": {
        "/public": {
            "get": {
                "operationId": "publicEndpoint",
                "security": [],
            }
        },
        "/protected": {
            "get": {
                "operationId": "protectedEndpoint",
                "security": [{"bearer": []}],
            }
        },
    },
    "components": {
        "securitySchemes": {
            "bearer": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
            }
        }
    },
}


@dataclass
class FakeResponse:
    status_code: int
    headers: dict[str, str]
    json_payload: dict | None = None
    text_payload: str = ""

    @property
    def text(self) -> str:
        return self.text_payload

    def json(self):
        if self.json_payload is None:
            raise ValueError("No JSON")
        return self.json_payload


class TestAuthenticatedDebugRequest:
    @pytest.fixture(autouse=True)
    def setup_spec_and_env(self, monkeypatch):
        store = get_store()
        store.set_spec(SAMPLE_SPEC)
        debug_request._TOKEN_CACHE.clear()

        monkeypatch.setenv("API_BASE_URL", "https://api.example.com")
        monkeypatch.setenv("AUTH_LOGIN_PATH", "/auth/login")
        monkeypatch.setenv("AUTH_LOGIN_METHOD", "POST")
        monkeypatch.setenv("AUTH_LOGIN_BODY_MODE", "json")
        monkeypatch.setenv("AUTH_USERNAME_FIELD", "username")
        monkeypatch.setenv("AUTH_PASSWORD_FIELD", "password")
        monkeypatch.setenv("AUTH_TOKEN_PATH", "access_token")
        monkeypatch.setenv("AUTH_HEADER_NAME", "Authorization")
        monkeypatch.setenv("AUTH_HEADER_PREFIX", "Bearer")
        monkeypatch.setenv("AUTH_DEFAULT_USER", "")
        monkeypatch.setenv("AUTH_ROLE_MAP_JSON", '{"tutor":"tutor_user"}')
        monkeypatch.setenv(
            "AUTH_CREDENTIALS_JSON",
            '{"tutor_user":{"username":"tutor@example.com","password":"secret123"}}',
        )

    def test_public_request_without_auth(self, monkeypatch):
        calls = []

        def fake_request(*, method, url, params=None, json=None, data=None, headers=None, timeout=None):
            calls.append(
                {
                    "method": method,
                    "url": url,
                    "params": params,
                    "json": json,
                    "data": data,
                    "headers": headers or {},
                }
            )
            return FakeResponse(
                status_code=200,
                headers={
                    "content-type": "application/json",
                    "x-request-id": "req-1",
                    "authorization": "should-not-leak",
                },
                json_payload={"ok": True},
            )

        monkeypatch.setattr(debug_request.requests, "request", fake_request)

        result = debug_request.authenticated_debug_request(
            path="/public",
            method="GET",
            auth=False,
        )

        assert result["ok"] is True
        assert result["status"] == 200
        assert result["body"] == {"ok": True}
        assert result["response_headers"] == {
            "content-type": "application/json",
            "x-request-id": "req-1",
        }
        assert result["request"]["auth_used"] is False
        assert calls[0]["headers"] == {}
        assert len(calls) == 1

    def test_public_request_strips_authorization_header(self, monkeypatch):
        calls = []

        def fake_request(*, method, url, params=None, json=None, data=None, headers=None, timeout=None):
            calls.append(
                {
                    "method": method,
                    "url": url,
                    "params": params,
                    "json": json,
                    "data": data,
                    "headers": headers or {},
                }
            )
            return FakeResponse(
                status_code=200,
                headers={"content-type": "application/json"},
                json_payload={"ok": True},
            )

        monkeypatch.setattr(debug_request.requests, "request", fake_request)

        result = debug_request.authenticated_debug_request(
            path="/public",
            method="GET",
            auth=False,
            headers={"Authorization": "Bearer stale-token", "X-Trace-Id": "trace-1"},
        )

        assert result["ok"] is True
        assert "Authorization" not in calls[0]["headers"]
        assert "authorization" not in calls[0]["headers"]
        assert calls[0]["headers"] == {"X-Trace-Id": "trace-1"}

    def test_authenticated_request_by_explicit_user(self, monkeypatch):
        calls = []

        def fake_request(*, method, url, params=None, json=None, data=None, headers=None, timeout=None):
            calls.append({"method": method, "url": url, "json": json, "headers": headers or {}})
            if url.endswith("/auth/login"):
                return FakeResponse(
                    status_code=200,
                    headers={"content-type": "application/json"},
                    json_payload={"access_token": "token-user"},
                )
            return FakeResponse(
                status_code=200,
                headers={"content-type": "application/json"},
                json_payload={"ok": True},
            )

        monkeypatch.setattr(debug_request.requests, "request", fake_request)

        result = debug_request.authenticated_debug_request(
            path="/protected",
            method="GET",
            auth_user="tutor_user",
        )

        assert result["ok"] is True
        assert result["request"]["auth_used"] is True
        assert calls[0]["url"].endswith("/auth/login")
        assert calls[1]["headers"]["Authorization"] == "Bearer token-user"
        assert "token-user" not in str(result)

    def test_login_default_flow_uses_user_identifier(self, monkeypatch):
        calls = []

        monkeypatch.setenv("API_BASE_URL", "")
        monkeypatch.setenv("API_URL", "http://takt_api:8000/api/v1")
        monkeypatch.setenv("AUTH_LOGIN_PATH", "/api/v1/auth/login-default")
        monkeypatch.setenv("AUTH_LOGIN_BODY_MODE", "single_field")
        monkeypatch.setenv("AUTH_LOGIN_IDENTIFIER_FIELD", "user_identifier")

        def fake_request(*, method, url, params=None, json=None, data=None, headers=None, timeout=None):
            calls.append({"method": method, "url": url, "json": json, "data": data, "headers": headers or {}})
            if url.endswith("/auth/login-default"):
                assert json == {"user_identifier": "TUT4D7J"}
                return FakeResponse(
                    status_code=200,
                    headers={"content-type": "application/json"},
                    json_payload={"access_token": "token-default"},
                )
            return FakeResponse(
                status_code=200,
                headers={"content-type": "application/json"},
                json_payload={"ok": True},
            )

        monkeypatch.setattr(debug_request.requests, "request", fake_request)

        result = debug_request.authenticated_debug_request(
            path="/protected",
            method="GET",
            auth_user="TUT4D7J",
        )

        assert result["ok"] is True
        assert calls[0]["url"].endswith("/auth/login-default")
        assert calls[0]["json"] == {"user_identifier": "TUT4D7J"}
        assert calls[1]["headers"]["Authorization"] == "Bearer token-default"

    def test_concrete_path_matches_template_path(self, monkeypatch):
        calls = []
        store = get_store()
        store.set_spec(
            {
                "openapi": "3.0.0",
                "servers": [{"url": "https://api.example.com"}],
                "security": [{"bearer": []}],
                "paths": {
                    "/api/v1/tutors/{tutor_id}/students": {
                        "get": {
                            "operationId": "getTutorStudents",
                            "security": [{"bearer": []}],
                        }
                    }
                },
                "components": {
                    "securitySchemes": {
                        "bearer": {"type": "http", "scheme": "bearer"}
                    }
                },
            }
        )

        def fake_request(*, method, url, params=None, json=None, data=None, headers=None, timeout=None):
            calls.append({"method": method, "url": url, "json": json, "headers": headers or {}})
            if url.endswith("/auth/login-default"):
                return FakeResponse(
                    status_code=200,
                    headers={"content-type": "application/json"},
                    json_payload={"access_token": "token-template"},
                )
            return FakeResponse(
                status_code=200,
                headers={"content-type": "application/json"},
                json_payload={"ok": True},
            )

        monkeypatch.setattr(debug_request.requests, "request", fake_request)
        monkeypatch.setenv("API_URL", "http://takt_api:8000/api/v1")
        monkeypatch.setenv("AUTH_LOGIN_PATH", "/api/v1/auth/login-default")
        monkeypatch.setenv("AUTH_LOGIN_BODY_MODE", "single_field")
        monkeypatch.setenv("AUTH_LOGIN_IDENTIFIER_FIELD", "user_identifier")

        result = debug_request.authenticated_debug_request(
            path="/api/v1/tutors/T_TUT4D7J/students",
            method="GET",
            auth_user="TUT4D7J",
        )

        assert result["ok"] is True
        assert calls[1]["headers"]["Authorization"] == "Bearer token-template"

    def test_authenticated_request_by_role(self, monkeypatch):
        calls = []

        def fake_request(*, method, url, params=None, json=None, data=None, headers=None, timeout=None):
            calls.append({"method": method, "url": url, "headers": headers or {}})
            if url.endswith("/auth/login"):
                return FakeResponse(
                    status_code=200,
                    headers={"content-type": "application/json"},
                    json_payload={"access_token": "token-role"},
                )
            return FakeResponse(
                status_code=200,
                headers={"content-type": "application/json"},
                json_payload={"ok": True},
            )

        monkeypatch.setattr(debug_request.requests, "request", fake_request)

        result = debug_request.authenticated_debug_request(
            path="/protected",
            method="GET",
            auth_role="tutor",
        )

        assert result["ok"] is True
        assert calls[1]["headers"]["Authorization"] == "Bearer token-role"

    def test_auth_user_wins_over_role(self, monkeypatch):
        calls = []

        def fake_request(*, method, url, params=None, json=None, data=None, headers=None, timeout=None):
            calls.append({"method": method, "url": url, "json": json, "headers": headers or {}})
            if url.endswith("/auth/login"):
                username = (json or {}).get("username") or (data or {}).get("username")
                token = f"token-{username}"
                return FakeResponse(
                    status_code=200,
                    headers={"content-type": "application/json"},
                    json_payload={"access_token": token},
                )
            return FakeResponse(
                status_code=200,
                headers={"content-type": "application/json"},
                json_payload={"ok": True},
            )

        monkeypatch.setattr(debug_request.requests, "request", fake_request)
        monkeypatch.setenv(
            "AUTH_CREDENTIALS_JSON",
            '{"explicit_user":{"username":"explicit@example.com","password":"secret"}}',
        )
        monkeypatch.setenv("AUTH_ROLE_MAP_JSON", '{"tutor":"tutor_user"}')

        result = debug_request.authenticated_debug_request(
            path="/protected",
            method="GET",
            auth_user="explicit_user",
            auth_role="tutor",
        )

        assert result["ok"] is True
        assert calls[0]["json"]["username"] == "explicit@example.com"
        assert calls[1]["headers"]["Authorization"] == "Bearer token-explicit@example.com"

    def test_auth_failure_is_structured(self, monkeypatch):
        monkeypatch.setenv("AUTH_ROLE_MAP_JSON", "{}")

        def fake_request(*args, **kwargs):
            raise AssertionError("requests should not be called")

        monkeypatch.setattr(debug_request.requests, "request", fake_request)

        result = debug_request.authenticated_debug_request(
            path="/protected",
            method="GET",
            auth_role="missing-role",
        )

        assert result["ok"] is False
        assert result["error"]["type"] == "auth_error"
        assert result["error"]["code"] == "AUTH_ROLE_UNKNOWN"

    def test_token_reuse_in_same_process(self, monkeypatch):
        calls = []

        def fake_request(*, method, url, params=None, json=None, data=None, headers=None, timeout=None):
            calls.append({"method": method, "url": url, "headers": headers or {}})
            if url.endswith("/auth/login"):
                return FakeResponse(
                    status_code=200,
                    headers={"content-type": "application/json"},
                    json_payload={"access_token": "cached-token"},
                )
            return FakeResponse(
                status_code=200,
                headers={"content-type": "application/json"},
                json_payload={"ok": True},
            )

        monkeypatch.setattr(debug_request.requests, "request", fake_request)

        first = debug_request.authenticated_debug_request(
            path="/protected",
            method="GET",
            auth_user="tutor_user",
        )
        second = debug_request.authenticated_debug_request(
            path="/protected",
            method="GET",
            auth_user="tutor_user",
        )

        assert first["ok"] is True
        assert second["ok"] is True
        assert len([call for call in calls if call["url"].endswith("/auth/login")]) == 1

    def test_http_error_response_is_returned_normally(self, monkeypatch):
        def fake_request(*, method, url, params=None, json=None, data=None, headers=None, timeout=None):
            if url.endswith("/auth/login"):
                return FakeResponse(
                    status_code=200,
                    headers={"content-type": "application/json"},
                    json_payload={"access_token": "token-user"},
                )
            return FakeResponse(
                status_code=401,
                headers={"content-type": "application/json", "x-request-id": "req-401"},
                json_payload={"detail": "unauthorized"},
            )

        monkeypatch.setattr(debug_request.requests, "request", fake_request)

        result = debug_request.authenticated_debug_request(
            path="/protected",
            method="GET",
            auth_user="tutor_user",
        )

        assert result["ok"] is True
        assert result["status"] == 401
        assert result["body"] == {"detail": "unauthorized"}
        assert result["response_headers"] == {
            "content-type": "application/json",
            "x-request-id": "req-401",
        }


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
