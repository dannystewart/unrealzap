# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog], and this project adheres to [Semantic Versioning].

## [0.1.0] (2025-04-09)

### Added

- Adds GitHub Actions workflow for automating PyPI package publishing when version tags are created.
- Adds pre-commit configuration with ruff, mypy, and code quality hooks to ensure consistent code quality.
- Adds GPL-3.0 license file to clearly communicate how this can be used and shared.

### Changed

- Renames project from "Bug Zapper Kill Tracker" to "Unreal Zap" - now 100% more unreal.
- Simplifies installation process to use pip instead of Poetry, because life's complicated enough already.
- Modernizes project structure with improved package organization and updated dependencies for Python 3.12.
- Enhances code with better type annotations, timezone-aware datetime handling, and pathlib for file operations.
- Relocates sound files (dominating, double_kill, first_blood, etc.) to src/unrealzap/sounds/ directory. Same epic™ sounds, tidier organization.

### Removed

- Removes GitHub Pages documentation workflow that was fighting a losing battle with pyalsaaudio dependencies.

<!-- Links -->
[Keep a Changelog]: https://keepachangelog.com/en/1.1.0/
[Semantic Versioning]: https://semver.org/spec/v2.0.0.html

<!-- Versions -->
[0.1.0]: https://github.com/dannystewart/bug-zapper/releases/tag/v0.1.0
