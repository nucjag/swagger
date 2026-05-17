"""
Live authenticated debug request tool.

Implements: authenticatedDebugRequest (S12)
"""

from __future__ import annotations

import json
import os
import time
from typing import Any
from urllib.parse import urljoin, urlparse

import requests

from core.spec_store import get_store
from tools.contract import get_endpoint_contract

_TOKEN_CACHE: dict[str, str] = {}
_SAFE_RESPONSE_HEADERS = {
    "cache-control",
    "content-type",
    "content-length",
    "date",
    "etag",
    "x-correlation-id",
    "x-request-id",
    "x-trace-id",
}


class AuthError(Exception):
    """Structured auth failure."""

    def __init__(self, message: str, code: str):
        super().__init__(message)
        self.code = code


def authenticated_debug_request(
    path: str,
    method: str,
    query: dict[str, Any] | None = None,
    body: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    auth: bool = True,
    auth_user: str | None = None,
    auth_role: str | None = None,
) -> dict[str, Any]:
    """
    Execute a live HTTP request with optional auth.
    """
    spec_store = get_store()
    if not spec_store.is_loaded():
        return _error_result(
            "spec_error",
            "OpenAPI spec is not loaded",
            code="SPEC_NOT_LOADED",
        )

    try:
        contract_path = _resolve_contract_path(spec_store, path=path, method=method)
        contract = get_endpoint_contract(spec_store, path=contract_path, method=method)
    except KeyError as exc:
        return _error_result("spec_error", str(exc), code="ENDPOINT_NOT_FOUND")

    spec = spec_store.get_spec() or {}
    request_url = _build_request_url(_resolve_api_base_url(spec), path)
    auth_mode = "public"
    token = None
    request_headers = dict(headers or {})

    if auth:
        try:
            identity = _resolve_identity(auth_user=auth_user, auth_role=auth_role)
        except AuthError as exc:
            return _error_result("auth_error", str(exc), code=exc.code)
        requires_auth = _endpoint_requires_auth(spec, contract)

        if requires_auth and identity is None:
            return _error_result(
                "auth_error",
                "Authentication is required but no identity is configured",
                code="AUTH_IDENTITY_MISSING",
            )

        if identity is not None:
            auth_mode = identity["mode"]
            try:
                token = _get_cached_token(spec, identity)
            except AuthError as exc:
                return _error_result("auth_error", str(exc), code=exc.code)

            header_name = _env("AUTH_HEADER_NAME", "Authorization")
            header_prefix = _env("AUTH_HEADER_PREFIX", "Bearer")
            request_headers[header_name] = (
                f"{header_prefix} {token}" if header_prefix else token
            )
    else:
        auth_mode = "public"
        request_headers.pop("Authorization", None)
        request_headers.pop("authorization", None)

    request_headers = _normalise_request_headers(request_headers)

    try:
        elapsed_start = time.perf_counter()
        response = requests.request(
            method=method.upper(),
            url=request_url,
            params=query or None,
            json=body if body is not None else None,
            headers=request_headers,
            timeout=30,
        )
        elapsed_ms = int((time.perf_counter() - elapsed_start) * 1000)
    except requests.RequestException as exc:
        return _error_result("request_error", str(exc), code="NETWORK_ERROR")

    return {
        "ok": True,
        "status": response.status_code,
        "response_headers": _selected_response_headers(response.headers),
        "body": _parse_response_body(response),
        "elapsed_ms": elapsed_ms,
        "request": {
            "method": method.upper(),
            "url": request_url,
            "auth_used": auth and token is not None,
            "auth_mode": auth_mode,
        },
    }


def _error_result(error_type: str, message: str, code: str) -> dict[str, Any]:
    return {
        "ok": False,
        "error": {"type": error_type, "code": code, "message": message},
    }


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default)


def _load_json_env(name: str) -> dict[str, Any]:
    raw_value = _env(name, "{}")
    if not raw_value or raw_value in ("{}", "[]"):
        return {}
    try:
        parsed = json.loads(raw_value)
    except json.JSONDecodeError as exc:
        raise AuthError("Auth configuration JSON is invalid", code="AUTH_CONFIG_INVALID") from exc
    if not isinstance(parsed, dict):
        raise AuthError("Auth configuration must be a JSON object", code="AUTH_CONFIG_INVALID")
    return parsed


def _resolve_api_base_url(spec: dict[str, Any]) -> str:
    api_base_url = _env("API_BASE_URL")
    if api_base_url:
        return api_base_url.rstrip("/")

    api_url = _env("API_URL")
    if api_url:
        parsed_api_url = urlparse(api_url.rstrip("/"))
        if parsed_api_url.scheme and parsed_api_url.netloc:
            return f"{parsed_api_url.scheme}://{parsed_api_url.netloc}"
        return api_url.rstrip("/")

    servers = spec.get("servers", [])
    if servers:
        url = servers[0].get("url", "")
        if url:
            return url.rstrip("/")

    openapi_spec_url = _env("OPENAPI_SPEC_URL", "http://localhost:8087/openapi.json").rstrip("/")
    parsed = urlparse(openapi_spec_url)
    if parsed.scheme and parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}"

    return openapi_spec_url


def _build_request_url(base_url: str, path: str) -> str:
    if path.startswith("http://") or path.startswith("https://"):
        return path
    if not base_url:
        return path
    return urljoin(base_url.rstrip("/") + "/", path.lstrip("/"))


def _resolve_identity(
    auth_user: str | None, auth_role: str | None
) -> dict[str, str] | None:
    if auth_user:
        return {"mode": "user", "user": auth_user}

    if auth_role:
        role_map = _load_json_env("AUTH_ROLE_MAP_JSON")
        resolved_user = role_map.get(auth_role)
        if not resolved_user:
            raise AuthError(f"Unknown auth role: {auth_role}", code="AUTH_ROLE_UNKNOWN")
        return {"mode": "role", "role": auth_role, "user": resolved_user}

    default_user = _env("AUTH_DEFAULT_USER")
    if default_user:
        return {"mode": "default", "user": default_user}

    return None


def _get_cached_token(spec: dict[str, Any], identity: dict[str, str]) -> str:
    cache_key = _identity_cache_key(spec, identity)
    cached_token = _TOKEN_CACHE.get(cache_key)
    if cached_token:
        return cached_token

    credentials_map = _load_json_env("AUTH_CREDENTIALS_JSON")
    user_name = identity["user"]
    credentials = credentials_map.get(user_name)

    token = _login_and_extract_token(spec, user_name=user_name, credentials=credentials)
    _TOKEN_CACHE[cache_key] = token
    return token


def _login_and_extract_token(
    spec: dict[str, Any],
    user_name: str,
    credentials: dict[str, Any] | None,
) -> str:
    login_path = _env("AUTH_LOGIN_PATH", "/auth/login")
    login_url = _build_request_url(_resolve_api_base_url(spec), login_path)
    login_body_mode = _env("AUTH_LOGIN_BODY_MODE", "json").lower()
    login_method = _env("AUTH_LOGIN_METHOD", "POST").upper()

    try:
        if login_body_mode == "single_field":
            payload = {_env("AUTH_LOGIN_IDENTIFIER_FIELD", "user_identifier"): user_name}
            response = requests.request(
                method=login_method,
                url=login_url,
                json=payload,
                timeout=30,
            )
        elif login_body_mode == "form":
            payload = _build_credential_payload(credentials)
            response = requests.request(
                method=login_method,
                url=login_url,
                data=payload,
                timeout=30,
            )
        else:
            payload = _build_credential_payload(credentials)
            response = requests.request(
                method=login_method,
                url=login_url,
                json=payload,
                timeout=30,
            )
    except requests.RequestException as exc:
        raise AuthError(f"Login flow failed: {exc}", code="AUTH_LOGIN_UNREACHABLE") from exc

    if response.status_code >= 400:
        raise AuthError(
            f"Login flow returned HTTP {response.status_code}",
            code="AUTH_LOGIN_FAILED",
        )

    token = _extract_token(response)
    if not token:
        raise AuthError("Login response did not include an access token", code="AUTH_TOKEN_MISSING")
    return token


def _build_credential_payload(credentials: dict[str, Any] | None) -> dict[str, Any]:
    if not credentials:
        raise AuthError(
            "No credentials configured for the selected identity",
            code="AUTH_CREDENTIALS_MISSING",
        )

    payload: dict[str, Any] = {}
    username = credentials.get("username")
    password = credentials.get("password")
    if username is not None:
        payload[_env("AUTH_USERNAME_FIELD", "username")] = username
    if password is not None:
        payload[_env("AUTH_PASSWORD_FIELD", "password")] = password
    return payload


def _extract_token(response: requests.Response) -> str:
    token_path = _env("AUTH_TOKEN_PATH", "access_token").strip()

    if token_path:
        try:
            payload = response.json()
        except ValueError as exc:
            raise AuthError("Login response is not JSON", code="AUTH_TOKEN_PARSE_FAILED") from exc

        token_value: Any = payload
        for part in token_path.split("."):
            if isinstance(token_value, dict) and part in token_value:
                token_value = token_value[part]
            else:
                token_value = None
                break

        if isinstance(token_value, str):
            return token_value.strip()
        if token_value is not None:
            return str(token_value).strip()

    return response.text.strip()


def _endpoint_requires_auth(spec: dict[str, Any], contract: dict[str, Any]) -> bool:
    if "security" in contract:
        return len(contract.get("security") or []) > 0
    return len(spec.get("security") or []) > 0


def _selected_response_headers(headers: Any) -> dict[str, str]:
    selected: dict[str, str] = {}
    for key, value in dict(headers).items():
        if key.lower() in _SAFE_RESPONSE_HEADERS:
            selected[key] = value
    return selected


def _parse_response_body(response: requests.Response) -> Any:
    content_type = response.headers.get("content-type", "")
    if "application/json" in content_type.lower():
        try:
            return response.json()
        except ValueError:
            return response.text

    body_text = response.text
    return body_text if body_text else None


def _normalise_request_headers(headers: dict[str, str]) -> dict[str, str]:
    return {key: value for key, value in headers.items() if value is not None}


def _resolve_contract_path(spec_store, path: str, method: str) -> str:
    if spec_store.get_spec() is None:
        raise KeyError("Spec not loaded")

    spec_paths = (spec_store.get_spec() or {}).get("paths", {})
    if path in spec_paths and method.lower() in spec_paths[path]:
        return path

    for candidate_path, path_item in spec_paths.items():
        if method.lower() not in path_item:
            continue
        if _path_matches_template(candidate_path, path):
            return candidate_path

    raise KeyError(f"Endpoint not found: {method.upper()} {path}")


def _path_matches_template(template_path: str, actual_path: str) -> bool:
    template_parts = [part for part in template_path.strip("/").split("/") if part]
    actual_parts = [part for part in actual_path.strip("/").split("/") if part]

    if len(template_parts) != len(actual_parts):
        return False

    for template_part, actual_part in zip(template_parts, actual_parts, strict=True):
        if template_part.startswith("{") and template_part.endswith("}"):
            continue
        if template_part != actual_part:
            return False

    return True


def _identity_cache_key(spec: dict[str, Any], identity: dict[str, str]) -> str:
    user = identity.get("user", "")
    mode = identity.get("mode", "")
    role = identity.get("role", "")
    api_base_url = _resolve_api_base_url(spec)
    login_path = _env("AUTH_LOGIN_PATH", "/auth/login")
    login_method = _env("AUTH_LOGIN_METHOD", "POST")
    return f"{api_base_url}|{mode}|{user}|{role}|{login_path}|{login_method}"
