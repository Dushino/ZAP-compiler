# Test: Main Entry Point

**Purpose**: Validates that a ZAP program with a main entry point compiles correctly

## Feature
Program with main() procedure

## Test Code
Simple program with proc main() that performs no operations

## Expected Behavior
- Program compiles successfully
- Creates valid 6502 assembly
- Main procedure is present
- No errors or warnings

## Assembly Validation
- ✅ Contains `JSR MAIN` (call to main procedure)
- ✅ Contains `JMP *` (infinite loop - program halts)
- ✅ Contains `MAIN:` label
- ✅ Contains `RTS` instruction in main

## Memory Dump
No memory values to validate (program performs no operations)

## References
- Atari memory map: Programs stored from $4000
- Entry point: main() procedure
