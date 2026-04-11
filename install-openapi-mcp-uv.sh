#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "${SCRIPT_DIR}/../../.." && pwd)"
VENV_DIR="${SCRIPT_DIR}/.venv"
REQ_FILE="${SCRIPT_DIR}/requirements.txt"
SWAGGER_ENV_FILE="${SCRIPT_DIR}/.env"
SWAGGER_ENV_EXAMPLE="${SCRIPT_DIR}/.env.example"

install_uv() {
  echo "uv not found. Installing uv..."

  if command -v curl >/dev/null 2>&1; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
  elif command -v wget >/dev/null 2>&1; then
    wget -qO- https://astral.sh/uv/install.sh | sh
  else
    echo "ERROR: Neither curl nor wget found, cannot install uv automatically." >&2
    exit 1
  fi

  export PATH="${HOME}/.local/bin:${PATH}"

  if ! command -v uv >/dev/null 2>&1; then
    echo "ERROR: uv installation finished, but 'uv' is still not in PATH." >&2
    echo "Add ~/.local/bin to PATH and rerun this script." >&2
    exit 1
  fi
}

echo "OpenAPI MCP uv setup"
echo "===================="
echo "Project root: ${PROJECT_ROOT}"
echo "Swagger dir:  ${SCRIPT_DIR}"

if ! command -v uv >/dev/null 2>&1; then
  install_uv
fi

echo "Using uv: $(uv --version)"

echo "Creating venv (with pip): ${VENV_DIR}"
uv venv --seed "${VENV_DIR}"

echo "Installing dependencies from ${REQ_FILE}"
uv pip install --python "${VENV_DIR}/bin/python" -r "${REQ_FILE}"

if [[ ! -f "${SWAGGER_ENV_FILE}" && -f "${SWAGGER_ENV_EXAMPLE}" ]]; then
  cp "${SWAGGER_ENV_EXAMPLE}" "${SWAGGER_ENV_FILE}"
  echo "Created ${SWAGGER_ENV_FILE} from .env.example"
fi

echo "===================="
echo "Setup complete."
echo "Run server:"
echo "  bash ${SCRIPT_DIR}/start-openapi-mcp.sh"
