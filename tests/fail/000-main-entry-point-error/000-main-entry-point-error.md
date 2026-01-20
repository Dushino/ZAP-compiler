# Error Test: Missing Main Procedure

**Error Type**: Semantic Error - No main procedure defined

## Expected Error Pattern
```
Error: Program must have a 'main()' procedure
```

## What This Tests
- Compiler detects missing main() entry point
- Error message is clear and human-readable
- Error guides user to fix (add proc main())

## Error Message Quality
- ✅ Specific about what's wrong (missing main)
- ✅ Clear about what is required (main() procedure)
- ✅ Human-readable language
- ✅ Actionable (user knows what to do)

## Related Feature
Main entry point requirement - every ZAP program must have a main() procedure
