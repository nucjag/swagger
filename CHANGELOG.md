# Changelog

All notable changes for the Swagger MCP module are documented in this file.

## [1.2.0] - 2026-05-17

### Added
- S12 authenticated debug request flow with project login, token extraction, and process-local token reuse.
- New auth/file-upload story materials and related module updates.

### Changed
- MCP OpenAPI runtime compatibility improvements for Codex wrapper flow.
- Publish flow now excludes internal `.sdd/` artifacts from public `swagger` repository while keeping them in source repo.

### Security
- Public publish path is hardened to avoid leaking internal SDD working artifacts.

## [1.1.0] - 2026-04-26

### Added
- Story-based tooling set: `searchEndpoints`, `getEndpointContract`, `resolveSchema`, `generateClient`, `generateTests`, `generateMockData`, `validateRequest`, `getAuthInfo`.
- FastMCP base infrastructure, spec loading/parsing/caching, and in-memory store.
- UV installer, start scripts, and test/documentation reorganization.
- Subtree publish workflow for public Swagger module delivery.

## Historical Commits

- `443f56c` feat(s1): Initialize FastMCP infrastructure for OpenAPI MCP Server
- `5ab8fa9` feat(s2): Implement spec loading, parsing, and caching
- `f17a913` feat(s3): Add optimized in-memory store with endpoint and schema access
- `8c89116` feat(s4): Implement searchEndpoints tool with query/tags/method filtering
- `2e91603` feat(s5): Implement getEndpointContract tool with full contract extraction
- `0d9fb26` feat(s6): Implement resolveSchema tool with recursive $ref resolution
- `5111f82` feat(s7): Implement generateClient tool with TypeScript code generation
- `68994a2` feat(s9): Implement generateMockData tool with JSON Schema mock generation
- `5e1458c` chore: reorganize swagger tests to tests/ and add .gitignore
- `51c6c99` Добавлен uv-установщик swagger MCP и обновлены запуск/документация
- `37e072c` ruff + release notes
- `b0e94d7` feat(s10): Implement validateRequest tool with JSON Schema validation
- `e6f8a47` feat(s11): Implement getAuthInfo tool with auth scheme extraction
- `b5c3a98` feat(s8): Implement generateTests tool with Jest code generation
- `ab60af1` chore(swagger): add release subtree publish flow and drop tracked pyc cache
- `ca27386` docs(sdd): Story 0.0 spec + wiki-brief artifacts for SDD+Wiki integration
- `15bd2fd` chore(release): v1.1.0
- `2e14e00` Сделалил обёртку для запуска codex и доработали mcp openapi для совместимости с codex
- `c184c77` feat(swagger): новые стори для авторизации и загрузки файлов
- `64612a4` feat(s12): authenticated debug request wrap-up
- `7bdbc30` обновили список нужных плагинов
