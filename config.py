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
OPENAPI_SPEC_URL = os.getenv("OPENAPI_SPEC_URL", "http://localhost:8087/openapi.json")

MCP_PORT = int(os.getenv("MCP_PORT", "9999"))

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

SPEC_CACHE_PATH = str(Path(__file__).parent / "openapi.local.json")

# Validate required configuration
if not OPENAPI_SPEC_URL:
    raise ValueError(
        "OPENAPI_SPEC_URL is required. Set it in .env or as an environment variable.\n"
        "Example: OPENAPI_SPEC_URL=http://localhost:8087/openapi.json"
    )

__all__ = ["OPENAPI_SPEC_URL", "MCP_PORT", "LOG_LEVEL", "SPEC_CACHE_PATH"]
