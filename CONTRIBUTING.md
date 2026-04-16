# Contributing to ZAP! Compiler

The author of this software stands in solidarity with 🇺🇦 Ukraine. 
We believe in a world where international borders are respected and human rights are upheld. 
We encourage all users of this software to contribute to humanitarian efforts in 🇺🇦 Ukraine.

Thank you for your interest in contributing to the ZAP! compiler! This document explains how to report bugs, request features, and submit pull requests.

---

## Table of Contents

1. [Bug Reports](#bug-reports)
2. [Feature Requests](#feature-requests)
3. [Pull Request Rules](#pull-request-rules)
4. [Commit Messages](#commit-messages)
5. [Code of Conduct](#code-of-conduct)
6. [Getting Help](#getting-help)

---

## Bug Reports

### Required Information

- **ZAP! source code** — a minimal `.zap` file that reproduces the problem (strip out everything unrelated)
- **Compiler command** — exact flags used (e.g., `zapc -6502 -O1 bug.zap -o bug.s`)
- **What happened** — the actual compiler output, error message, or generated assembly
- **What should have happened** — expected behavior or correct output
- **Environment** — OS, Python version (if running from source), ZAP! version (`zapc --version`)

### Good Bug Report Example

```
File: bug.zap
---
byte x = 10
proc main()
    if x > 5
        x = 0
    end
end
---
Command: zapc -6502 -O1 bug.zap -o bug.s
Result: Compiler crashes with "IndexError: list index out of range"
Expected: Should compile successfully
Environment: Windows 11, zapc 1.0
```

### What Makes a Good Report

- The `.zap` file compiles (or fails) on its own — no external dependencies unless using standard library
- If the bug is in generated code, include the relevant `.s` output and describe what the 6502 code does wrong
- If the bug only appears with specific flags (e.g., only with `-O1`, or only with `-6502`), say so explicitly
- One bug per issue — don't combine unrelated problems

### Suggested Labels

`bug`, `crash`, `codegen`, `optimizer`, `parser`, `sema`

---

## Feature Requests

- Describe the feature and **why** it's useful for 6502/Atari development
- Show a proposed syntax example in ZAP! code
- Note if this affects the grammar (`docs/grammar.ebnf`), standard library, or code generation
- Consider backward compatibility — will existing programs still compile?

---

## Pull Request Rules

### Before You Start

- Open an issue first to discuss non-trivial changes — this avoids wasted effort if the design doesn't fit
- One PR per feature or fix — don't bundle unrelated changes
- Base your branch on `main`

### Code Requirements

- **Python 3.x** compatible, no external dependencies in the compiler itself (PyInstaller is build-only)
- Follow existing code style — no auto-formatters that rewrite untouched code
- Add docstring comments before new functions/methods
- Never break the compilation pipeline order: preprocessor → modules → tokenizer → parser → sema → constsubst → constfold → DCE → codegen → jump threading → label cleanup

### Testing Requirements (Mandatory)

Every PR must pass the full test suite. Run:

**Windows:**
```batch
make.bat tests
```

**Linux/macOS:**
```bash
make tests
```

All 4 variants are tested for each pass test (65C02, 6502, 65C02+O1, 6502+O1). **All must pass.**

#### Prerequisites for Running Tests Locally

To run the full suite you need:

- **Python 3.x** — to run the ZAP! compiler
- **cc65 toolchain** (`ca65`, `ld65`, `da65`) — to assemble and link. See [cc65.github.io](https://cc65.github.io/) for installation
- **6502 simulator** (`6502_simulator` in `PATH`) — runs compiled binaries and produces memory dumps for reference comparison. Without it every positive test will fail with `[SIM_ERROR]`. Install from https://github.com/Dushino/6502_simulator:
  ```bash
  pip install git+https://github.com/Dushino/6502_simulator.git
  # pip installs as '6502-simulator' (hyphen); the Makefile expects underscore
  ln -sf "$(command -v 6502-simulator)" ~/.local/bin/6502_simulator
  ```

See [tests/README.md](tests/README.md) for more details on the test harness and how to create new tests.

#### For New Features — Add Tests

At least one **pass test** in `tests/pass/NNN-descriptive-name/`:
- `NNN-descriptive-name.zap` — test source
- `NNN-descriptive-name.json` — simulator config (`max_cycles`, `dump_memory` ranges)
- `NNN-descriptive-name.ref` — expected memory dump output

At least one **fail test** in `tests/fail/NNN-descriptive-name/`:
- `NNN-descriptive-name.zap` — source that must fail
- `NNN-descriptive-name.err` — expected error message with correct line:column

#### For Bug Fixes — Add a Regression Test

- A pass test that would have failed before your fix, or
- A fail test that verifies the correct error is now reported

#### Test Numbering

Use the next available number in sequence. Check existing directories before choosing a number.

#### Fail Test Error Format

The `.err` file first line must match the compiler's error output exactly, including line and column numbers. Example:
```
3:5: error: Use of uninitialized variable 'X'
```

### ASM Block Rules

- `ASM...END` blocks must never be modified by optimizer passes
- Only `__ZAP_*` prefixed labels are compiler-internal — all other labels in ASM blocks are user-controlled and must be preserved verbatim

### Documentation Requirements

For any change that affects language syntax, semantics, or compiler behavior:

- Update `docs/ZAP_LANGUAGE_REFERENCE.md` — the language spec
- Update `docs/grammar.ebnf` — if grammar rules changed
- Update `docs/ERROR_MESSAGES.md` — if new errors are introduced
- Update `docs/KNOWN_LIMITATIONS.md` — if a limitation is removed or added
- Update `docs/STDLIB.md` — if standard library functions changed
- Cross-check examples in `examples/` still compile
- Cross-check IDE extension in `IDE_Integration/` (syntax highlighting covers new keywords, etc.)

### Standard Library Changes

- Platform-agnostic code goes in `lib/` root (e.g., `string.zap`, `stdio.zap`)
- Atari-specific code goes in `lib/atari/`
- New library functions need documentation in `docs/STDLIB.md`
- Library changes must not break existing programs that `.include` the library

### What NOT to Include in a PR

- IDE/editor config files (`.vscode/`, `.idea/`)
- Build artifacts (`*.o`, `*.com`, `*.xex`, `dist/`, `__pycache__/`)
- Unrelated formatting or style changes to files you didn't modify
- Changes to `PROGRESS.md` — maintainer will update this on merge

---

## Commit Messages

- Use imperative mood: "Fix word comparison codegen" not "Fixed" or "Fixes"
- First line under 72 characters
- If the change is non-trivial, add a blank line and a short explanation of **why**
- Reference the issue number: "Fix #42: off-by-one in for loop codegen"

---

## Code of Conduct

- Be respectful and constructive
- This is a hobby/educational project — patience is appreciated
- Focus on the code, not the person
- Questions are welcome — there are no stupid questions about 6502 programming

---

## Getting Help

- **Questions about ZAP! language:** open a Discussion (not an Issue)
- **Compiler internals:** see `docs/ARCHITECTURE.md`
- **Test failures:** include the full test output and which variant failed (6502/65C02/O1)

---

**Ready to contribute? Fork the repo, create a branch, and submit a PR!**
