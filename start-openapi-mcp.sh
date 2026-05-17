#!/usr/bin/env bash
set -euo pipefail

# OpenAPI MCP Server startup script
# Loads OpenAPI spec from URL and starts FastMCP server

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "${SCRIPT_DIR}/../../.." && pwd)"
SPEC_DIR="${SCRIPT_DIR}"
SPEC_FILE="${SPEC_DIR}/openapi.local.json"
TMP_FILE="${SPEC_FILE}.tmp"
VENV_PYTHON_312="${SPEC_DIR}/.venv312/bin/python"

MCP_SCRIPT="${SPEC_DIR}/openapi-mcp-server.py"
ENV_FILE="${PROJECT_ROOT}/.env"
SWAGGER_ENV_FILE="${SPEC_DIR}/.env"
DEFAULT_SPEC_URL="http://localhost:8087/openapi.json"

# Keep FastMCP from emitting banner/update output on stdio transports.
export FASTMCP_SHOW_SERVER_BANNER="${FASTMCP_SHOW_SERVER_BANNER:-false}"
export FASTMCP_CHECK_FOR_UPDATES="${FASTMCP_CHECK_FOR_UPDATES:-off}"

# stdout must stay reserved for MCP stdio traffic.
echo "Starting OpenAPI MCP server..." >&2
echo "===============================" >&2

mkdir -p "${SPEC_DIR}"

SPEC_URL="${DEFAULT_SPEC_URL}"

read_env_value() {
  local env_file="$1"
  local key="$2"
  local value=""

  [[ -f "${env_file}" ]] || return 0

  value="$(grep -m1 -E "^${key}=" "${env_file}" | cut -d= -f2- | sed 's/^["\x27]//;s/["\x27]$//' || true)"
  printf "%s" "${value}"
}

# Key-level fallback: root .env first, local .env only for missing key
ROOT_ENV_SPEC_URL="$(read_env_value "${ENV_FILE}" "OPENAPI_SPEC_URL")"
SWAGGER_ENV_SPEC_URL="$(read_env_value "${SWAGGER_ENV_FILE}" "OPENAPI_SPEC_URL")"

if [[ -n "${ROOT_ENV_SPEC_URL}" ]]; then
  SPEC_URL="${ROOT_ENV_SPEC_URL}"
elif [[ -n "${SWAGGER_ENV_SPEC_URL}" ]]; then
  SPEC_URL="${SWAGGER_ENV_SPEC_URL}"
fi

echo "OPENAPI_SPEC_URL: ${SPEC_URL}" >&2

# Try to download spec
download_ok=0
if command -v curl >/dev/null 2>&1; then
  if curl -fsSL --connect-timeout 5 --max-time 20 "${SPEC_URL}" -o "${TMP_FILE}"; then
    download_ok=1
  fi
elif command -v wget >/dev/null 2>&1; then
  if wget -qO "${TMP_FILE}" "${SPEC_URL}"; then
    download_ok=1
  fi
fi

if [[ "${download_ok}" -eq 1 ]]; then
  if [[ -x "${VENV_PYTHON_312}" ]]; then
    JSON_PYTHON="${VENV_PYTHON_312}"
  elif command -v python3 >/dev/null 2>&1; then
    JSON_PYTHON="python3"
  else
    echo "✗ ERROR: Python not found (need python3 or ${VENV_PYTHON_312})" >&2
    exit 1
  fi

  if "${JSON_PYTHON}" -m json.tool "${TMP_FILE}" >/dev/null 2>&1; then
    mv "${TMP_FILE}" "${SPEC_FILE}"
    echo "✓ Spec downloaded and validated: ${SPEC_FILE}" >&2
  else
    rm -f "${TMP_FILE}"
    echo "⚠ WARNING: Invalid JSON from ${SPEC_URL}, using cached spec" >&2
  fi
else
  rm -f "${TMP_FILE}" 2>/dev/null || true
  echo "⚠ WARNING: Failed to download spec from ${SPEC_URL}" >&2
  echo "  Using cached spec if available: ${SPEC_FILE}" >&2
fi

if [[ ! -s "${SPEC_FILE}" ]]; then
  echo "✗ ERROR: No local spec available at ${SPEC_FILE}" >&2
  echo "  Please ensure OPENAPI_SPEC_URL is set and reachable." >&2
  exit 1
fi

echo "===============================" >&2
echo "Starting FastMCP server..." >&2
echo "===============================" >&2

# Change to swagger dir so imports work correctly
cd "${SPEC_DIR}"

if [[ -x "${VENV_PYTHON_312}" ]]; then
  PYTHON_BIN="${VENV_PYTHON_312}"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="python3"
else
  echo "✗ ERROR: Python not found (need python3 or ${VENV_PYTHON_312})" >&2
  exit 1
fi

# Run the MCP server (unbuffered stdio for deterministic MCP transport)
exec "${PYTHON_BIN}" -u "${MCP_SCRIPT}"
