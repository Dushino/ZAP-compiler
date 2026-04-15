## Summary

<!-- Briefly describe what this PR changes and why. -->

## Type of change

- [ ] Bug fix (non-breaking change that fixes an issue)
- [ ] New feature (non-breaking change that adds functionality)
- [ ] Breaking change (fix or feature that would cause existing programs to behave differently)
- [ ] Documentation update
- [ ] Refactoring / internal cleanup
- [ ] Standard library change
- [ ] IDE extension change

## Related issue

<!-- Reference the issue this PR addresses, e.g. "Fixes #42" -->

## Tests

- [ ] I added a regression test (pass test, fail test, or both)
- [ ] I ran the full test suite (`make tests` / `make.bat tests`) and all 4 variants pass
  - [ ] 65C02 default
  - [ ] 6502 (`-6502`)
  - [ ] 65C02 + O1 (`-O1`)
  - [ ] 6502 + O1 (`-6502 -O1`)
- [ ] For new features: added at least one test in `tests/pass/` and one in `tests/fail/`
- [ ] For fail tests: `.err` file matches the compiler's output exactly (line:column included)

## Documentation

If this PR changes language syntax, semantics, or compiler behavior, please confirm:

- [ ] Updated `docs/ZAP_LANGUAGE_REFERENCE.md` (if language changed)
- [ ] Updated `docs/grammar.ebnf` (if grammar changed)
- [ ] Updated `docs/ERROR_MESSAGES.md` (if new errors added)
- [ ] Updated `docs/KNOWN_LIMITATIONS.md` (if a limitation changed)
- [ ] Updated `docs/STDLIB.md` (if standard library changed)
- [ ] Updated `examples/` (if relevant)
- [ ] Updated IDE extension in `IDE_Integration/` (if syntax/keywords changed)

## Checklist

- [ ] My code follows the existing style of the project
- [ ] I added docstring comments to new functions/methods
- [ ] I did not modify `ASM...END` blocks in any optimizer pass
- [ ] I did not include build artifacts (`*.o`, `*.com`, `*.xex`, `dist/`, `__pycache__/`)
- [ ] I did not include unrelated formatting changes
- [ ] I read [CONTRIBUTING.md](../CONTRIBUTING.md)
