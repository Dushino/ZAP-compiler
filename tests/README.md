# ZAP Compiler Test Suite

## Directory Structure

```
tests/
├── pass/          Tests that SHOULD compile successfully
└── fail/          Tests that SHOULD fail compilation (negative tests)
```

## Running Tests

```bash
make tests
```

This will:
1. Compile all `.zap` files in `tests/pass/` - expecting success
2. Compile all `.zap` files in `tests/fail/` - expecting failure
3. Report summary with pass/fail counts
4. Exit with status 1 if any test behaves incorrectly

## Test Results

- **✓ PASS**: Test behaved as expected
- **✗ FAIL**: Test behaved incorrectly:
  - A should-pass test failed to compile (shows first 5 lines of error)
  - A should-fail test compiled successfully

## Adding New Tests

### Positive Tests (should compile)
Add `.zap` files to `tests/pass/`

### Negative Tests (should fail)
Add `.zap` files to `tests/fail/`

Examples of negative tests:
- Duplicate identifiers
- Type errors
- Syntax errors
- Semantic violations

## Current Test Coverage

**Positive tests (1):**
- test_variables_decl.zap - Variable declarations with various modifiers

**Negative tests (6):**
- test_dup.zap - Duplicate global variable names
- test_dup_define.zap - Duplicate .define symbols
- test_dup_func_param.zap - Duplicate function parameters
- test_dup_local.zap - Duplicate local variables
- test_dup_param.zap - Duplicate procedure parameters
- test_dup_param_local.zap - Parameter/local name collision
