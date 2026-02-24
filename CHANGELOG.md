# Changelog

All notable changes to Coolaw DeskFlow will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Planned
- Windows/Linux cross-platform support
- E2E testing with Playwright
- Auto-update feature (Tauri updater)
- HNSW vector index for memory retrieval
- Multi-Agent collaboration (Master/Worker)
- IM channel integrations (Feishu, WeWork, DingTalk)

---

## [0.1.0] - 2026-02-24

### Added

#### Core Engine
- Agent main controller with tool-use loop
- Brain (LLM client) with multi-provider failover
  - Anthropic Claude adapter
  - OpenAI Compatible adapter
  - DashScope (Qwen) adapter
- Prompt assembler with token budget management
- Ralph Loop (never-give-up retry mechanism)
- Task monitor for runtime metrics

#### Memory System
- SQLite storage with FTS5 full-text search
- LRU cache (L1, 1000 entries)
- Multi-path retriever with time-decay ranking
- Memory manager unified interface

#### Tool System
- Tool registry and executor
- Built-in tools:
  - Shell (with command blocklist)
  - File (with path sandbox)
  - Web (HTTP requests + HTML extraction)
- Parallel tool execution with dependency analysis

#### Desktop App (Tauri + React)
- Chat View with streaming output
- Settings View for LLM configuration
- Monitor View for status dashboard
- App Shell (Title Bar, Sidebar, Status Bar)
- Dark mode design system (Fira Code + Fira Sans)

#### CLI
- `deskflow init` - Interactive setup wizard
- `deskflow chat` - Interactive REPL
- `deskflow serve` - Start API server
- `deskflow status` - View component status
- `deskflow config` - Configuration management

#### API
- POST /api/chat - Chat endpoint
- WebSocket /api/chat/stream - Streaming endpoint
- GET /api/health - Health check
- GET /api/config - Configuration endpoint
- Rate limiting middleware

#### Documentation
- README.md - Project overview
- CONTRIBUTING.md - Contribution guide
- ARCHITECTURE.md - Technical architecture
- PROJECT_STATUS.md - Project status report
- docs/api.md - API reference
- docs/configuration.md - Configuration guide
- docs/developer-guide.md - Developer guide

#### Identity System
- SOUL.md - Core values
- AGENT.md - Capability definition
- USER.md - User preferences
- MEMORY.md - Long-term memory summary
- 4 persona presets (default, butler, tech_expert, business)

#### Skills System
- 60+ system skills
- Skill installation from GitHub
- Skill documentation (SKILL.md for each skill)

### Changed
- N/A (Initial release)

### Deprecated
- N/A

### Removed
- N/A

### Fixed
- Tauri beforeBuildCommand infinite recursion (fixed in build config)
- TypeScript module resolution errors in ChatView/SkillsView
- Unused imports in chatStore.ts and useChat.ts

### Security
- No hardcoded secrets in source code
- Shell command blocklist implemented
- File path sandbox implemented
- Input validation via Pydantic

---

## [0.0.1] - 2026-02-21

### Added
- Initial project setup
- Project structure and configuration
- Basic dependencies

---

## Version History

| Version | Date | Status | Notes |
|---------|------|--------|-------|
| 0.1.0 | 2026-02-24 | Released | MVP release |
| 0.0.1 | 2026-02-21 | Initial | Project setup |

---

## Upcoming Releases

### v0.2.0 (Planned: 2026-03)
- [ ] Identity system with proactive greetings
- [ ] Skill sandbox execution
- [ ] Daily memory consolidation
- [ ] Self-evolution engine

### v0.3.0 (Planned: 2026-04)
- [ ] IM channel integrations
- [ ] Multi-Agent collaboration
- [ ] MCP protocol support

### v1.0.0 (Planned: 2026-06)
- [ ] Production-ready stability
- [ ] Complete documentation
- [ ] Skill marketplace

---

**Maintained by**: Coolaw DeskFlow Team
**License**: MIT
