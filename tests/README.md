# ZAP Compiler Test Suite

;
; The author of this software stands in solidarity with 🇺🇦 Ukraine. 
; We believe in a world where international borders are respected and human rights are upheld. 
; We encourage all users of this software to contribute to humanitarian efforts in 🇺🇦 Ukraine.


## Overview

The test suite provides comprehensive validation of the ZAP compiler across multiple optimization levels and CPU targets. Tests are executed in alphabetical order, allowing you to organize them by complexity using naming conventions like `001_test_name.zap`, `002_test_name.zap`, etc.

## Directory Structure

```
tests/
├── pass/          Tests that SHOULD compile and run successfully
│   ├── *.zap      Test source files
│   ├── *.ref      Reference output files (REQUIRED for each test)
│   └── *.json     Configuration file for simulator (REQUIRED for each test)
└── fail/          Tests that SHOULD fail compilation (negative tests)
    └── *.zap      Test source files
```

## Running Tests

### Linux/Unix
```bash
make tests
```

### Windows
```batch
make.bat tests
```

## Test Execution Flow

For each positive test (in `tests/pass/`), the test suite:

1. **Requires a `.ref` file** - Each test must have a corresponding `.ref` reference file containing expected simulator output
2. **Tests 4 compilation variants**:
   - Default (65C02 target)
   - `--O1`  (optimizations)
   - `-6502` (NMOS 6502 target)
   - `-6502 --O1` (NMOS 6502 with optimizations)
3. **For each variant**:
   - Compiles ZAP → assembly (detects ZAP compiler errors)
   - Assembles → object file with ca65 (detects CA65 errors)
   - Assembles Atari header file (detects CA65 errors)
   - Links with ld65 (detects LD65 errors)
   - Creates binary and cuts header (skip first 6 bytes)
   - Disassembles with da65
   - **Runs in 6502 simulator** and dumps memory (40000-40120 hex)
   - **Compares output with `.ref` file** (detects OUTPUT_MISMATCH errors)
4. **Reports results** - Pass only if all 4 variants succeed and outputs match reference

For negative tests (in `tests/fail/`):
- Attempts to compile with `-6502`
- Must fail to pass the test
- Success is "correctly rejected"

## Test Results Output

Each test shows one of these results:

**✓ PASS (all 4 variants)**
- All 4 compilation variants succeeded
- All simulator outputs matched the reference file

**✗ FAIL (X/4 variants failed)**
- One or more variants failed
- Shows error codes for debugging:
  - `[ZAP_ERROR]` - ZAP compiler failed to compile
  - `[CA65_ERROR]` - ca65 assembler failed
  - `[LD65_ERROR]` - ld65 linker failed
  - `[SIM_ERROR]` - 6502 simulator failed to run
  - `[OUTPUT_MISMATCH]` - Simulator output doesn't match `.ref` file

## Creating Reference Files

When you create a new test in `tests/pass/`:

1. Create your test file: `tests/pass/001_my_test.zap`
2. Compile and run manually to generate reference output:
   ```bash
   python3 compiler.py tests/pass/001_my_test.zap -o test.s
   ca65 -I lib -t none --cpu 65c02 -g test.s -o test.o
   ca65 -I lib -t none --cpu 65c02 -g lib/atari/exehdr.s -o exehdr.o
   ld65 -C cfg/my_atari.cfg test.o exehdr.o -o test.com
   6502_simulator --cpu 65c02 --config tests/pass/001_my_test.json --verbose --dump-file tests/pass/001_my_test.ref test.com
   ```
3. Verify the reference output is correct
4. Run `make tests` to validate

## Adding New Tests

### Positive Tests (should compile and pass)

1. Add `.zap` file to `tests/pass/` with a name like `001_feature_name.zap`
2. Create a `.ref` reference file with expected simulator output
3. Example test file:
   ```zap
   ; tests/pass/001_simple_math.zap
   PROC main()
     BYTE result
     result = 2 + 3
   RETURN
   ```

### Negative Tests (should fail)

1. Add `.zap` file to `tests/fail/` with a name like `test_invalid_syntax.zap`
2. No reference file needed - test passes if compilation fails
3. Examples:
   - Duplicate identifiers
   - Type errors
   - Syntax errors
   - Semantic violations

## Current Test Status

**Positive Tests:**
- Status: In `tests/pass/todo/` (pending .ref file creation)
- Tests awaiting reference files:
  - test_variables_decl.zap
  - test_math_1.zap
  - test_cmp.zap (has .ref file)
  - test_hardware_vars.zap (has .ref file)
  - test_variables_optimiz.zap

**Negative Tests (6) - All Ready:**
- ✓ test_dup.zap - Duplicate global variable names
- ✓ test_dup_define.zap - Duplicate .define symbols
- ✓ test_dup_func_param.zap - Duplicate function parameters
- ✓ test_dup_local.zap - Duplicate local variables
- ✓ test_dup_param.zap - Duplicate procedure parameters
- ✓ test_dup_param_local.zap - Parameter/local name collision

## Test Organization

To organize tests by complexity, use numeric prefixes:

```
tests/pass/
├── 001_simple_math.zap
├── 002_variable_operations.zap
├── 003_functions.zap
├── 004_procedures.zap
├── 005_arrays.zap
├── 010_advanced_features.zap
...
```

This ensures tests run from simple to complex, making it easier to debug compilation issues.
- test_dup_define.zap - Duplicate .define symbols
- test_dup_func_param.zap - Duplicate function parameters
- test_dup_local.zap - Duplicate local variables
- test_dup_param.zap - Duplicate procedure parameters
- test_dup_param_local.zap - Parameter/local name collision
