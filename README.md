# ZAP! — A High-Level Language for 6502 / Atari 8-bit

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-0.9.4-orange.svg)](version.py)
[![Tests](https://github.com/Dushino/ZAP-compiler/actions/workflows/test.yml/badge.svg)](https://github.com/Dushino/ZAP-compiler/actions/workflows/test.yml)
[![Docs](https://img.shields.io/badge/docs-dushino.github.io-blue.svg)](https://dushino.github.io/ZAP-compiler/)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)

The author of this software stands in solidarity with 🇺🇦 Ukraine. 
We believe in a world where international borders are respected and human rights are upheld. 
We encourage all users of this software to contribute to humanitarian efforts in 🇺🇦 Ukraine.

---

**ZAP!** is a modern high-level language that compiles to **6502 / 65C02 assembly**, targeting **Atari 8-bit** computers. It combines high-level constructs (structs, enums, functions, loops) with low-level control (pointers, hardware registers, inline assembly) and produces tight, optimized 6502 code.

In benchmark comparisons, ZAP! generates code that runs **~44% faster than Action!** on the Atari 8-bit platform — see [benchmarks/BENCHMARKS.md](benchmarks/BENCHMARKS.md).

## Documentation

**Full documentation lives at [dushino.github.io/ZAP-compiler](https://dushino.github.io/ZAP-compiler/)** — with ZAP! syntax highlighting, search, and sidebar navigation.

- [Getting Started Guide](https://dushino.github.io/ZAP-compiler/GETTING_STARTED.html) — beginner tutorial, installation, and first program
- [Language Reference](https://dushino.github.io/ZAP-compiler/ZAP_LANGUAGE_REFERENCE.html) — complete language spec
- [Advanced Topics](https://dushino.github.io/ZAP-compiler/ADVANCED_TOPICS.html) — pointers, inline assembly, optimization
- [Standard Library](https://dushino.github.io/ZAP-compiler/STDLIB.html) — built-in functions and modules
- [Error Messages](https://dushino.github.io/ZAP-compiler/ERROR_MESSAGES.html) — compiler error catalog
- [Known Limitations](https://dushino.github.io/ZAP-compiler/KNOWN_LIMITATIONS.html) — current limitations
- [Architecture](https://dushino.github.io/ZAP-compiler/ARCHITECTURE.html) — how the compiler works internally
- [IDE Integration](https://dushino.github.io/ZAP-compiler/IDE_INTEGRATION.html) — VS Code / Antigravity setup

## Contributing

Contributions are welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) before opening an issue or pull request — it explains how to file good bug reports, what tests to add, and which docs to update.

See also:

- [Code of Conduct](CODE_OF_CONDUCT.md)
- [Security Policy](SECURITY.md)
- [Changelog](CHANGELOG.md)

## License

ZAP! is released under the [GNU General Public License v3.0](LICENSE).
