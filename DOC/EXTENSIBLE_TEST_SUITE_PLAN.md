# Extensible Test Suite - Implementation Plan

**Date**: January 20, 2026  
**Status**: ✅ Backup Complete, ⏳ Structure Setup In Progress

## Overview

We are creating an extensible test suite for all ZAP language features. This document outlines the structure and process.

## Current Status

✅ **Tests Backup**: All original tests backed up to `./tests-backup/`  
✅ **Feature Checklist**: Comprehensive feature list in `EXTENSIBLE_TEST_SUITE_CHECKLIST.md`  
⏳ **Next**: Set up directory structure in `./tests/pass/`

## Test Suite Structure

### Directory Organization

```
./tests/
├── pass/
│   ├── 000-main-entry-point/              # Main entry point test
│   ├── 001-byte-type/                     # BYTE type
│   ├── 002-word-type/                     # WORD type
│   ├── 003-byte-pointers/                 # Byte pointer basics
│   ├── 004-word-pointers/                 # Word pointer basics
│   ├── 005-arrays-1d-byte/                # 1D byte arrays
│   ├── 006-arrays-1d-word/                # 1D word arrays
│   ├── 007-arrays-multidim-2d/            # 2D arrays
│   ├── 008-arrays-multidim-3d/            # 3D arrays
│   ├── 009-arrays-inferred-size/          # Inferred array size
│   ├── 010-arrays-string-init/            # String initialization
│   ├── 011-pointers-dereference/          # Pointer dereference
│   ├── 012-pointers-arithmetic/           # Pointer arithmetic
│   ├── 013-address-of-operator/           # Address-of (@)
│   ├── 014-structs-simple/                # Simple structs
│   ├── 015-structs-nested/                # Nested structs
│   ├── 016-structs-arrays/                # Arrays of structs
│   ├── 017-structs-pointers/              # Pointers to structs
│   ├── 018-procedures-basic/              # Procedures (no params)
│   ├── 019-procedures-parameters/         # Procedures with parameters
│   ├── 020-functions-basic/               # Functions
│   ├── 021-functions-return-values/       # Functions with returns
│   ├── 022-control-flow-if-else/          # If-then-else
│   ├── 023-control-flow-while/            # While loops
│   ├── 024-control-flow-for/              # For loops
│   ├── 025-control-flow-break/            # Break statement
│   ├── 026-operators-arithmetic/          # Arithmetic operators
│   ├── 027-operators-bitwise/             # Bitwise operators
│   ├── 028-operators-comparison/          # Comparison operators
│   ├── 029-operators-logical/             # Logical operators
│   ├── 030-expressions-complex/           # Complex expressions
│   ├── 031-initialization-arrays/         # Array initialization
│   ├── 032-initialization-structs/        # Struct initialization
│   ├── 033-const-scalar/                  # Const scalars
│   ├── 034-const-arrays/                  # Const arrays
│   ├── 035-const-structs/                 # Const structs
│   ├── 036-fixed-address-variables/       # @address variables
│   ├── 037-global-local-scope/            # Global vs local variables
│   ├── 038-string-literals/               # String literals
│   ├── 039-escape-sequences/              # Escape sequences
│   └── ... (more tests as needed)
└── fail/
    └── (failure test cases - preserved from backup)
```

## Test File Format

### Passing Tests: `./tests/pass/NNN-feature-name/`

Each test directory contains:

```
NNN-feature-name/
├── source.zap          # Valid ZAP source code
├── source.ref          # Expected memory dump (reference)
├── source.json         # Simulator configuration file
└── description.txt     # Test description (optional)
```

**source.zap**
- Complete, compilable ZAP program
- Tests specific feature(s)
- Should be minimal but complete
- Must compile successfully

**source.ref**
- Memory dump showing expected state after execution
- Format: (to be defined with first test)
- Shows BSS, ROM, or final register states

**source.json**
- 6502 simulator configuration
- Specifies memory ranges, breakpoints, etc.
- Used to set up simulation environment

**description.txt**
- Human-readable test description
- Purpose of test
- Expected behavior

### Failing Tests: `./tests/fail/NNN-feature-name-error/`

For each passing test feature, create a corresponding error test:

```
NNN-feature-name-error/
├── source.zap          # Invalid ZAP source (should fail to compile)
├── error.ref           # Expected compiler error message
└── description.txt     # Description of what error should occur
```

**source.zap**
- Code that violates language rules
- Should trigger compiler error
- Tests error detection and reporting
- Each file tests ONE specific error condition

**error.ref**
- Expected error message (or patterns to match)
- Checks that error message is human-readable
- Validates error location reporting (line numbers)

**Purpose of Error Tests**
- ✅ Verify error detection works correctly
- ✅ Validate error messages are clear and helpful
- ✅ Ensure line/column numbers are accurate
- ✅ Check for actionable error descriptions

## Test Execution Process

### For Passing Tests

1. **Compile**: `python compiler.py source.zap -o source.s`
2. **Assemble**: `ca65 source.s -o source.o`
3. **Link**: `ld65 source.o -o source.bin`
4. **Simulate**: Load `source.bin` in 6502_simulator with configuration `source.json`
5. **Verify**: Compare final memory state against `source.ref`
6. **Report**: ✅ Pass or ❌ Fail with diff

### For Failing Tests

1. **Compile**: `python compiler.py source.zap` (should fail)
2. **Capture**: Error output from compiler
3. **Verify**: Error message matches pattern in `error.ref`
4. **Validate**:
   - Error detected ✅
   - Message is human-readable ✅
   - Line number is correct ✅
5. **Report**: ✅ Error correctly caught or ❌ Error not caught/wrong message

## Current Status: Directory Locations

| Path | Status | Purpose |
|------|--------|---------|
| `./tests-backup/` | ✅ Ready | Backup of original tests |
| `./tests/pass/` | ✅ Ready | New passing tests (will be created) |
| `./tests/fail/` | ✅ Ready | Failing tests with error validation |
| `./tests/pass/NNN-*/source.json` | ⏳ New | Simulator config files (per test) |
| `./tests/fail/NNN-*-error/error.ref` | ⏳ New | Expected error patterns (per error test) |

## Implementation Phases

### Phase 1: Core Feature Tests (Checklist: Feature 1-6)
- [ ] Data types and declarations
- [ ] Arrays (1D and multi-dimensional)
- [ ] Pointers and dereferencing
- [ ] Structs (simple and nested)
- [ ] Procedures and functions
- [ ] Control flow

### Phase 2: Operators & Expressions (Checklist: Feature 7-8)
- [ ] Arithmetic operators
- [ ] Bitwise operators
- [ ] Comparison operators
- [ ] Logical operators
- [ ] String literals and escape sequences

### Phase 3: Advanced Features (Checklist: Feature 9-11)
- [ ] Initialization patterns
- [ ] Fixed address variables
- [ ] Const enforcement
- [ ] Comments and metadata

### Phase 4: Integration & Edge Cases (Checklist: Feature 12-13)
- [ ] Error cases and edge cases
- [ ] Complete integration tests
- [ ] Performance tests

## Next Steps

1. ✅ Create comprehensive feature checklist
2. ⏳ Create initial test directories (NNN-feature-name)
3. ⏳ Create first few test files with .zap and .ref
4. ⏳ Define .ref file format based on actual test
5. ⏳ Implement test runner/validator

---

**Status**: ✅ Ready for Phase 1 implementation  
**Checklist**: [EXTENSIBLE_TEST_SUITE_CHECKLIST.md](EXTENSIBLE_TEST_SUITE_CHECKLIST.md)  
**Backup Location**: `./tests-backup/`
