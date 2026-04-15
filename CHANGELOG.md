# Changelog

All notable changes to the ZAP! compiler will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **GitHub Pages documentation site** at `dushino.github.io/ZAP-compiler/` with full ZAP! syntax highlighting
  - Built with Jekyll + `just-the-docs` theme
  - Custom Prism.js language definition for ZAP! (`docs/assets/prism/prism-zap.js`)
  - Sidebar navigation, search, "Edit on GitHub" links
- "Docs" badge in `README.md` linking to the Pages site
- Public release preparation: `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`, `CHANGELOG.md`
- GitHub issue templates (bug report, feature request) and pull request template
- GitHub Actions CI workflow that runs the test suite on Ubuntu with cc65
- "Building the Compiler from Source" section in `docs/GETTING_STARTED.md`
- Link to `CONTRIBUTING.md` in `README.md`

### Changed

- **Renamed `DOC/` → `docs/`** to match GitHub Pages conventions. All references in README, CONTRIBUTING, PR template, etc. updated.
- `make_dist.bat` and `make_dist.sh` now respect `ZAPC_INSTALL_DIR` environment variable instead of hardcoded paths
- `work/go.bat` and `benchmarks/go.bat` now respect `ALTIRRA` environment variable instead of hardcoded paths
- IDE extension version aligned with compiler version (0.9.4)
- `.gitignore` extended to cover `.venv/`, generated `.s` files, PyInstaller artifacts, and Jekyll build artifacts under `docs/`

## [0.9.4] - 2026-04

### Added

- Local variable naming collision fix using `$` separator (`_PROC$VAR` instead of `_PROC_VAR`)
- ca65 `.FEATURE dollar_in_identifiers` emitted automatically in assembly header
- Standard library redesign with Atari CIO status codes for ERRNO
- Shared BCD print engine using 6502 SED double-dabble for `printb`/`printw`/`printl`
- `putxw` for word hex output
- Argument width validation for procedure and function calls
- `PEEK`/`POKE` built-in type validation
- Word-index array subscript support
- Sieve peephole optimizations (dead low-byte cmp, TMP2 elimination, inline ADD16, 65C02 indirect)
- New regression tests: 201–207

### Fixed

- Word-vs-constant comparison codegen (LT, LE, GT, GE all rewritten)
- Slot liveness / argument evaluation order bug for nested calls
- Double-mapped line number bug in error reporting
- TMP2 round-trip elimination for struct field stores
- ZP budget calculation: `zp_start + temps` instead of `max(zp_start, temps)`

## [0.9.0] - earlier

### Added

- Initial public-ready feature set
- 32-bit `LONG` support
- C-style pointer arithmetic
- Enum support
- `-ZPSTART` and `-cfg` CLI flags for zero-page budget control
- ZP overflow detection at compile time

[Unreleased]: https://github.com/Dushino/ZAP-compiler/compare/v0.9.4...HEAD
[0.9.4]: https://github.com/Dushino/ZAP-compiler/releases/tag/v0.9.4
[0.9.0]: https://github.com/Dushino/ZAP-compiler/releases/tag/v0.9.0
