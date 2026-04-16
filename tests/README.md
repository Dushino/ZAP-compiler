# ZAP! Compiler Test Suite

The author of this software stands in solidarity with 🇺🇦 Ukraine.
We believe in a world where international borders are respected and human rights are upheld.
We encourage all users of this software to contribute to humanitarian efforts in 🇺🇦 Ukraine.

---

## Overview

The test suite provides comprehensive validation of the ZAP! compiler across multiple optimization levels and CPU targets. Every positive test compiles in **four variants** (default 65C02, `-6502`, `-O1`, and `-6502 -O1`) to catch regressions across the full matrix of supported targets.

As of the current release, the suite contains roughly **175 positive tests** (in `tests/pass/`) and **139 negative tests** (in `tests/fail/`). The CI workflow runs the full suite on every push and pull request.

## Directory Structure

```
tests/
├── pass/          Tests that SHOULD compile, link, and produce expected output
│   └── NNN-descriptive-name/
│       ├── NNN-descriptive-name.zap    Test source
│       ├── NNN-descriptive-name.json   Simulator config (REQUIRED)
│       ├── NNN-descriptive-name.ref    Reference memory dump (REQUIRED)
│       └── NNN-descriptive-name.flags  (optional) extra compiler flags
└── fail/          Tests that SHOULD be rejected by the compiler
    └── descriptive-name/
        ├── descriptive-name.zap        Test source (must fail to compile)
        ├── descriptive-name.err        Expected error message (REQUIRED)
        └── descriptive-name.flags      (optional) extra compiler flags
```

Each test lives in its own subdirectory, numbered for positive tests (`001-` through the current count) to give a rough complexity ordering.

## Prerequisites

Before running the test suite locally you need:

- **Python 3.x** — to run the compiler
- **cc65 toolchain** (`ca65`, `ld65`, `da65`) — to assemble and link the generated code. Install via `apt-get install cc65` (Ubuntu/Debian), `brew install cc65` (macOS), or from https://cc65.github.io/ (Windows)
- **6502 simulator** — required by every positive test to run the compiled binary and produce a memory dump for comparison against the `.ref` file. Install it from https://github.com/Dushino/6502_simulator:
  ```bash
  pip install git+https://github.com/Dushino/6502_simulator.git
  ```
  The pip entry point installs as `6502-simulator` (hyphen). On Linux/macOS the `Makefile` expects `6502_simulator` (underscore) to be in `PATH` — create a symlink, e.g.:
  ```bash
  ln -sf "$(command -v 6502-simulator)" ~/.local/bin/6502_simulator
  ```
  On Windows, `make.bat` locates `6502_simulator.exe` in `PATH` — build a standalone binary with PyInstaller if you need that name exactly.

Without the simulator, all positive tests will fail with `[SIM_ERROR]` because there's nothing to produce the memory dump the test harness compares against. Negative tests (in `tests/fail/`) don't need the simulator — they only require the ZAP! compiler.

## Running Tests

### Linux/Unix
```bash
make tests
```

### Windows
```batch
make.bat tests
```

### Running a single directory

On Linux/Unix you can target a single test subdirectory:

```bash
make test pass/015-for-loop
```

## Test Execution Flow

For each positive test (in `tests/pass/NNN-name/`), the test harness:

1. **Checks for required files**: `.zap` (source), `.json` (simulator config), `.ref` (expected output)
2. **Compiles in 4 variants**:
   - Default (65C02 target, no optimization)
   - `-6502` (NMOS 6502 target, no optimization)
   - `-O1` (65C02 + peephole optimization)
   - `-6502 -O1` (NMOS 6502 + peephole optimization)
3. **For each variant**:
   - Compiles ZAP! → assembly with `zapc`
   - Assembles → object file with `ca65`
   - Assembles the Atari executable header (`lib/atari/exehdr.s`)
   - Links with `ld65` using `cfg/my_atari.cfg`
   - Runs the binary in the **6502 simulator** and dumps memory ranges specified in the `.json`
   - Compares the dump against the `.ref` file byte-for-byte
4. **Reports results** — pass only if all 4 variants succeed and all memory dumps match

For negative tests (in `tests/fail/`):

- Compiles with each of the 4 variants; every variant must **fail**
- If an `.err` file is present, the compiler's error output is compared against it (line:column must match the expected error)
- Test passes if all 4 variants correctly reject the source and the error message matches

## Test Results Output

Each test shows one of these results:

| Result | Meaning |
|---|---|
| ✅ **PASS (all 4 variants)** | Positive test: all 4 variants compiled, linked, ran, and memory dumps matched |
| ✅ **PASS (correctly rejected, error message verified)** | Negative test: compiler rejected all 4 variants with the expected error |
| ❌ **FAIL (X/4 variants failed)** | Positive test: one or more variants broke. Error codes indicate which stage |
| ❌ **FAIL (X/4 variants passed)** | Negative test: compiler incorrectly accepted code that should fail |
| ❌ **FAIL (wrong error message)** | Negative test: rejected but with the wrong error message |

Error codes in FAIL lines indicate the failing stage:

- `[ZAP_ERROR]` — ZAP! compiler crashed or rejected a positive test
- `[CA65_ERROR]` — ca65 assembler failed
- `[LD65_ERROR]` — ld65 linker failed
- `[DA65_ERROR]` — da65 disassembler failed (non-fatal, treated as a warning)
- `[SIM_ERROR]` — 6502 simulator couldn't run the binary
- `[OUTPUT_MISMATCH]` — memory dump didn't match the `.ref` file
- `[UNEXPECTED_PASS]` — negative test compiled without error (should have failed)
- `[MSG_MISMATCH]` — negative test rejected with the wrong error message

## Adding New Tests

### Positive Test

1. Pick the next available number: `ls tests/pass/` and pick `NNN+1`
2. Create a directory: `tests/pass/NNN-descriptive-name/`
3. Write your test source as `NNN-descriptive-name.zap`:
   ```zap
   byte result

   proc main()
       result = 2 + 3
   end
   ```
4. Create `NNN-descriptive-name.json` with simulator config:
   ```json
   {
       "max_cycles": 10000,
       "verbose": true,
       "dump_memory": ["0x4000-0x4007"]
   }
   ```
   The `dump_memory` ranges should cover the memory addresses your test populates. The test harness compares these ranges against the `.ref` file.
5. Generate the `.ref` file by running the compile-and-dump pipeline manually:
   ```bash
   cd tests/pass/NNN-descriptive-name
   python3 ../../../compiler.py NNN-descriptive-name.zap -o test.s
   ca65 -I ../../../lib -t none --cpu 65c02 -g test.s -o test.o
   ca65 -I ../../../lib -t none --cpu 65c02 -g ../../../lib/atari/exehdr.s -o exehdr.o
   ld65 -C ../../../cfg/my_atari.cfg test.o exehdr.o -o test.com
   6502_simulator --cpu 65c02 --config NNN-descriptive-name.json --verbose --dump-file NNN-descriptive-name.ref test.com
   ```
6. Inspect `NNN-descriptive-name.ref` to confirm the memory contents are what you expect
7. Run `make tests` (or `make test pass/NNN-descriptive-name` for just your test) to validate all 4 variants

### Negative Test

1. Create a directory: `tests/fail/descriptive-name/` (no numeric prefix required, but consistent numbering helps)
2. Write your test source as `descriptive-name.zap` — it must be rejected by the compiler
3. Create `descriptive-name.err` with the expected error output. The first line must match the compiler's output exactly, including line:column:
   ```
   3:5: error: Use of uninitialized variable 'X'
   ```
4. Run `make tests` — the test passes if all 4 variants are rejected and the error message matches

### Per-test compiler flags (optional)

If your test requires extra flags (for example `-ZPSTART 0x80` to reproduce a zero-page budget scenario), put them in a `.flags` file next to the `.zap`:

```
-ZPSTART 0x80
```

The test harness appends these to every variant's invocation.

## Naming Convention

Positive tests use `NNN-descriptive-name` where `NNN` is a zero-padded 3-digit number. Numeric prefixes keep tests running in a predictable order that roughly mirrors complexity. Negative tests can use any slug, though most match the positive test they correspond to (e.g., `025-structs-simple-error`).

Use dashes, not underscores, in directory and file names.
