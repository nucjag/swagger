# OpenAPI MCP Server

A FastMCP server that provides tools for working with OpenAPI specifications.

## Overview

This MCP server helps frontend developers by:

- Searching endpoints in OpenAPI specs
- Generating TypeScript clients and types
- Creating mock data for testing
- Generating Jest tests
- Validating API requests

## Installation

```bash
# From repository root:
bash .claude/mcp/swagger/install-openapi-mcp-uv.sh

# Script behavior:
# 1) Checks if uv is installed
# 2) Installs uv automatically if missing
# 3) Creates .claude/mcp/swagger/.venv (with pip seeded)
# 4) Installs dependencies from requirements.txt
# 5) Creates .claude/mcp/swagger/.env from .env.example if needed
```

### Verify Installation

```bash
# Option A: using uv (recommended)
uv pip show --python .claude/mcp/swagger/.venv/bin/python fastmcp mcp python-dotenv requests pydantic

# Option B: using pip inside seeded venv
.claude/mcp/swagger/.venv/bin/python -m pip show fastmcp mcp python-dotenv requests pydantic
```

## Configuration

Set `OPENAPI_SPEC_URL` in `.env` to point to your OpenAPI specification:

```bash
OPENAPI_SPEC_URL=http://localhost:8087/openapi.json
```

Environment priority is key-based:

1. Project root `.env` (`/home/f/00_code/sdd-factory/.env`) is primary.
2. Local `.claude/mcp/swagger/.env` is fallback only for keys missing in root `.env`.

## Running the Server

```bash
bash .claude/mcp/swagger/start-openapi-mcp.sh
```

This script will:

1. Download the OpenAPI spec from OPENAPI_SPEC_URL
2. Cache it locally in `openapi.local.json`
3. Start the FastMCP server (uses `.claude/mcp/swagger/.venv/bin/python` if present)

## Project Structure

```
.claude/mcp/swagger/
├── openapi-mcp-server.py      # FastMCP server entry point
├── config.py                  # Configuration management
├── install-openapi-mcp-uv.sh  # uv-based setup script
├── start-openapi-mcp.sh       # Server startup script
├── requirements.txt           # Python dependencies
├── .env                       # Configuration (local)
├── .env.example               # Configuration template
│
├── core/                      # Core utilities
│   ├── spec_loader.py        # Load and parse specs
│   ├── spec_store.py         # In-memory spec storage
│   └── utils.py              # Common utilities
│
├── tools/                     # MCP tool implementations
│   ├── search.py             # searchEndpoints
│   ├── contract.py           # getEndpointContract
│   ├── schema_resolver.py    # resolveSchema
│   ├── codegen.py            # generateClient
│   └── mock_generator.py     # generateMockData
│
└── openapi.local.json        # Cached OpenAPI spec
```

## Development

### Adding a new tool

1. Create a function in `tools/` directory
2. Register it in `openapi-mcp-server.py` using `@mcp.tool()` decorator
3. Implement the tool logic
4. Add unit tests

### Testing

```bash
pytest .claude/mcp/swagger -v
```

## Tools (MVP 1.0)

| Tool | Status | Purpose |
|------|--------|---------|
| searchEndpoints | Planned (S4) | Find endpoints by query, tags, method |
| getEndpointContract | Planned (S5) | Full request/response contract |
| resolveSchema | Planned (S6) | Expand $ref references |
| generateClient | Planned (S7) | Generate TypeScript code |
| generateMockData | Planned (S9) | Create realistic mock objects |

## Future Enhancements (v1.1+)

- validateRequest — Validate requests before sending
- getAuthInfo — Authentication details
- generateTests — Jest/pytest templates
- getFileUploadPattern — File upload handling
- compareVersions — Breaking changes detection
- Caching layer for parsed specs

## Release and Publishing

This module is developed in `sdd-factory` (feature/dev branches) and published to
`https://github.com/nucjag/swagger` as `main` only.

Release tag convention in `sdd-factory`:

- `swagger-vX.Y.Z`

Publish mechanism:

- Automated: GitHub Action on tag push (`swagger-v*`)
- Manual fallback: `./scripts/publish-swagger.sh`

Operational runbook:

- `docs/swagger-publish-runbook.md`
