# Error Test: Invalid BYTE Usage

**Error Type**: Semantic Error - Undefined variable reference

## Expected Error Pattern
```
Error: Undefined variable/expression error
```

## What This Tests
- Compiler detects references to undefined variables
- Error message identifies the missing variable

## Error Should Detect
- `undefined_variable` is not defined
- Cannot use undefined names in expressions
- Clear error about what's missing

## Related Feature
BYTE type - proper type checking and variable validation
