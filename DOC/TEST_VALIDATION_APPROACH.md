# Test Validation Approach

**Date**: January 20, 2026  
**Purpose**: Define dual-test strategy for comprehensive language validation  
**Status**: Framework Ready

## Overview

The extensible test suite uses a **dual-test approach**: for each language feature, we create both:

1. **Passing Test** - Validates feature works correctly
2. **Error Test** - Validates error detection and messages

This ensures not only correct compilation and execution, but also helpful error reporting.

## Dual-Test Strategy

### Category: Feature X (e.g., "001-byte-type")

#### Passing Test: `./tests/pass/001-byte-type/`
```
001-byte-type/
├── source.zap          # Valid byte declaration and usage
├── source.ref          # Expected memory state after execution
├── source.json         # Simulator configuration
└── description.txt     # Test purpose
```

**Validates:**
- ✅ Feature works as specified
- ✅ Code compiles without error
- ✅ Assembly output is correct
- ✅ Simulation produces expected memory state

#### Error Test: `./tests/fail/001-byte-type-error/`
```
001-byte-type-error/
├── source.zap          # Invalid byte usage (should fail)
├── error.ref           # Expected error message pattern
└── description.txt     # What error should occur
```

**Validates:**
- ✅ Compiler detects the error
- ✅ Error message is human-readable
- ✅ Line number is accurate
- ✅ Error message suggests how to fix

## Error Test Design

### One Error Per Test File

Each error test file tests **exactly one** error condition:

```zap
// 001-byte-type-error/source.zap

// ERROR: Assigning word to byte variable
byte x = 65535;  // Should error: value too large for byte
```

### Error Message Validation

The `error.ref` file contains patterns to match against compiler output:

```
# 001-byte-type-error/error.ref

ERROR: Semantic error at line 3
  Assigning WORD value (65535) to BYTE variable (x)
  Range check: value must be 0-255
```

### Benefits of Error Tests

| Benefit | Purpose |
|---------|---------|
| **Early Detection** | Catches regression when error handling is modified |
| **Documentation** | Shows what errors users should expect |
| **User Experience** | Ensures error messages guide users to fix problems |
| **Completeness** | Validates both success and failure paths |
| **Regression Prevention** | Prevents error messages from becoming less helpful |

## Test Execution Workflow

### Phase 1: Passing Tests
```
For each NNN-feature-name/ in ./tests/pass/:
  1. Compile source.zap → source.s
  2. Assemble source.s → source.o
  3. Link source.o → source.bin
  4. Simulate with source.json
  5. Compare memory to source.ref
  6. Report: PASS or FAIL
```

### Phase 2: Error Tests
```
For each NNN-feature-name-error/ in ./tests/fail/:
  1. Attempt to compile source.zap
  2. Capture error output
  3. Match against error.ref patterns
  4. Report: ERROR CORRECTLY CAUGHT or ERROR MISSED/WRONG
```

## Example: Complete Feature Test

### Feature: "Byte Type"

#### Passing Test (001-byte-type)
```zap
// tests/pass/001-byte-type/source.zap
proc main()
  byte x = 10
  byte y = 255
  byte z = x + y  // Valid: arithmetic wraps
.
```

**Expected Result**:
- ✅ Compiles successfully
- ✅ Allocates 3 bytes
- ✅ Initializes correctly
- ✅ z contains 9 (10 + 255 = 265, wraps to 9)

#### Error Test (001-byte-type-error)
```zap
// tests/fail/001-byte-type-error/source.zap
proc main()
  byte x = 256  // ERROR: value out of range
.
```

**Expected Result**:
- ✅ Compiler detects error
- ✅ Error message: "Value 256 exceeds BYTE range (0-255)"
- ✅ Line number accurate (line 3)
- ✅ Suggestion: "Use WORD type for larger values"

## Error Message Quality Checklist

For each error test, validate:

- [ ] Error is detected (compiler exits with error)
- [ ] Error message is specific (not generic)
- [ ] Line number is correct
- [ ] Column/position information provided (if applicable)
- [ ] Error message is actionable (suggests fix)
- [ ] Spelling and grammar are correct
- [ ] Message matches user's perspective (not internal jargon)

## Statistics

### Total Tests in Suite

- **200+ Passing Tests** - Validate features work correctly
- **100+ Error Tests** - Validate error detection and messages
- **300+ Total Tests** - Comprehensive coverage

### Test Organization

| Category | Passing | Error | Total |
|----------|---------|-------|-------|
| Data Types | 15 | 10 | 25 |
| Arrays | 30 | 15 | 45 |
| Pointers | 25 | 12 | 37 |
| Structs | 25 | 12 | 37 |
| Functions | 25 | 10 | 35 |
| Control Flow | 20 | 8 | 28 |
| Operators | 40 | 15 | 55 |
| Others | 20 | 18 | 38 |
| **Total** | **200** | **100** | **300** |

## Next Steps

1. Create first passing test (001-byte-type)
2. Create corresponding error test (001-byte-type-error)
3. Validate both tests
4. Repeat for each feature

---

**Related Documents:**
- [EXTENSIBLE_TEST_SUITE_CHECKLIST.md](EXTENSIBLE_TEST_SUITE_CHECKLIST.md) - Feature list
- [EXTENSIBLE_TEST_SUITE_PLAN.md](EXTENSIBLE_TEST_SUITE_PLAN.md) - Implementation roadmap
