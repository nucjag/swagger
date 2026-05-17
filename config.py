"""
Configuration for OpenAPI MCP Server.
Loads from .env or uses sensible defaults.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment with key-level fallback:
# 1) project root .env (primary)
# 2) local .claude/mcp/swagger/.env (fallback for missing keys)
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]
ROOT_ENV_PATH = PROJECT_ROOT / ".env"
LOCAL_ENV_PATH = SCRIPT_DIR / ".env"

if ROOT_ENV_PATH.exists():
    load_dotenv(ROOT_ENV_PATH, override=False)
if LOCAL_ENV_PATH.exists():
    load_dotenv(LOCAL_ENV_PATH, override=False)

# Configuration
API_URL = os.getenv("API_URL", "")
API_BASE_URL = os.getenv("API_BASE_URL", "")
OPENAPI_SPEC_URL = os.getenv("OPENAPI_SPEC_URL", "").strip()

if API_URL and (not OPENAPI_SPEC_URL or OPENAPI_SPEC_URL == "http://localhost:8087/openapi.json"):
    api_root = API_URL.rstrip("/")
    if api_root.endswith("/api/v1"):
        OPENAPI_SPEC_URL = f"{api_root[:-len('/api/v1')]}/openapi.json"
    else:
        OPENAPI_SPEC_URL = f"{api_root}/openapi.json"
elif not OPENAPI_SPEC_URL:
    OPENAPI_SPEC_URL = "http://localhost:8087/openapi.json"

MCP_PORT = int(os.getenv("MCP_PORT", "9999"))

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

AUTH_LOGIN_PATH = os.getenv("AUTH_LOGIN_PATH", "/api/v1/auth/login-default")
AUTH_LOGIN_METHOD = os.getenv("AUTH_LOGIN_METHOD", "POST")
AUTH_LOGIN_BODY_MODE = os.getenv("AUTH_LOGIN_BODY_MODE", "single_field")
AUTH_LOGIN_IDENTIFIER_FIELD = os.getenv("AUTH_LOGIN_IDENTIFIER_FIELD", "user_identifier")
AUTH_USERNAME_FIELD = os.getenv("AUTH_USERNAME_FIELD", "username")
AUTH_PASSWORD_FIELD = os.getenv("AUTH_PASSWORD_FIELD", "password")
AUTH_TOKEN_PATH = os.getenv("AUTH_TOKEN_PATH", "access_token")
AUTH_HEADER_NAME = os.getenv("AUTH_HEADER_NAME", "Authorization")
AUTH_HEADER_PREFIX = os.getenv("AUTH_HEADER_PREFIX", "Bearer")
AUTH_DEFAULT_USER = os.getenv("AUTH_DEFAULT_USER", "")
AUTH_ROLE_MAP_JSON = os.getenv("AUTH_ROLE_MAP_JSON", "{}")
AUTH_CREDENTIALS_JSON = os.getenv("AUTH_CREDENTIALS_JSON", "{}")

SPEC_CACHE_PATH = str(Path(__file__).parent / "openapi.local.json")

# Validate required configuration
if not OPENAPI_SPEC_URL:
    raise ValueError(
        "OPENAPI_SPEC_URL is required. Set it in .env or as an environment variable.\n"
        "Example: OPENAPI_SPEC_URL=http://localhost:8087/openapi.json"
    )

__all__ = [
    "API_BASE_URL",
    "API_URL",
    "AUTH_CREDENTIALS_JSON",
    "AUTH_DEFAULT_USER",
    "AUTH_HEADER_NAME",
    "AUTH_HEADER_PREFIX",
    "AUTH_LOGIN_BODY_MODE",
    "AUTH_LOGIN_METHOD",
    "AUTH_LOGIN_PATH",
    "AUTH_LOGIN_IDENTIFIER_FIELD",
    "AUTH_PASSWORD_FIELD",
    "AUTH_ROLE_MAP_JSON",
    "AUTH_TOKEN_PATH",
    "AUTH_USERNAME_FIELD",
    "LOG_LEVEL",
    "MCP_PORT",
    "OPENAPI_SPEC_URL",
    "SPEC_CACHE_PATH",
]
