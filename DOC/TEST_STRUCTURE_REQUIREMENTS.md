# Test Suite Structure - Final Clarification

**Date**: January 20, 2026  
**Status**: Tests 000 and 001 ready with proper naming and structure

## Critical Requirements (Confirmed by User)

### 1. Test Execution
- Tests are run via `make.bat tests` or `make tests`
- Compilation target: **Atari** (programs stored from $4000)
- Test validation: Memory dumps at specified addresses

### 2. Atari Memory Model
- **Program Storage**: $4000 (16384 decimal) and above
- **Test Value Storage**: Address 40000 decimal ($9C40)
- **Memory Validation**: simulator reads dump_memory ranges from .json file

### 3. File Naming Convention
- **All files must be named the same as their directory**
- **Only file extensions differ**

#### Example: test 001-byte-type
```
tests/pass/001-byte-type/
├── 001-byte-type.zap          (source code)
├── 001-byte-type.s            (generated assembly - created by compilation)
├── 001-byte-type.json         (simulator config)
├── 001-byte-type.ref          (expected output/memory dump)
└── 001-byte-type.md           (test description - NOT .txt!)
```

### 4. Description Files
- **Must be `.md` files** (Markdown)
- `.txt` files are deleted by `make clean`
- Descriptions in `.md` provide test documentation

### 5. Memory Dump Format
- **Defined in .json** file with `dump_memory` ranges
- **Address format**: Hex ranges like `["0x9C40-0x9C40"]`
- **Reference file (.ref)**: Shows expected memory values
- **For 000-main-entry-point**: Only shows addresses with 0x00 (no changes)

## Proper Test File Structure

### Passing Test Files

**001-byte-type.zap** (ZAP Source)
```zap
byte result @40000 = 0

proc main()
    byte x = 42
    byte y = 100
    byte z = x + y  ; 142
    result = z
end
```

**001-byte-type.json** (Simulator Config)
```json
{
    "max_cycles": 10000,
    "verbose": true,
    "dump_memory": ["0x9C40-0x9C40"]
}
```

**001-byte-type.ref** (Expected Memory Dump)
```markdown
# Memory Dump Validation

## Test Values
- x = 42
- y = 100
- z = 142 (42 + 100)
- result @40000 ($9C40) = 142 (0x8E)

## Expected Memory Dump
Address $9C40: 0x8E

## Validation
- ✅ Result stored correctly
```

**001-byte-type.md** (Test Description)
```markdown
# Test: BYTE Type Declaration and Usage

**Purpose**: Validates BYTE type variables work correctly

## Feature
BYTE data type for small integer values (0-255)

## Test Code
...
```

### Error Test Files

**001-byte-type-error.zap** (Invalid Code)
```zap
proc main()
    byte x = undefined_variable  ; ERROR: undefined
end
```

**001-byte-type-error.ref** (Expected Error)
```
ERROR_EXPECTED: Yes - undefined variable reference
ERROR_MESSAGE: Should mention "undefined" or "not defined"
SEVERITY: Semantic error
```

**001-byte-type-error.md** (Error Description)
```markdown
# Error Test: Invalid BYTE Usage

**Error Type**: Semantic Error

## Expected Error
Compiler should detect undefined variable and report error

...
```

## Current Test Status

### Test 000: main-entry-point ✅
- ✅ Passing test: `tests/pass/000-main-entry-point/000-main-entry-point.*`
- ✅ Error test: `tests/fail/000-main-entry-point-error/000-main-entry-point-error.*`
- ✅ File naming correct
- ✅ .md descriptions in place

### Test 001: byte-type ✅
- ✅ Passing test: `tests/pass/001-byte-type/001-byte-type.*`
  - source.zap (✅ valid code)
  - 001-byte-type.s (✅ compiled assembly)
  - 001-byte-type.json (✅ memory dump config)
  - 001-byte-type.ref (✅ expected memory values)
  - 001-byte-type.md (✅ description)
- ✅ Error test: `tests/fail/001-byte-type-error/001-byte-type-error.*`
  - source.zap (✅ invalid code)
  - 001-byte-type-error.ref (✅ error expectations)
  - 001-byte-type-error.md (✅ description)
- ✅ File naming correct
- ✅ .md descriptions in place

## Key Points for Future Tests

1. **Every test value must be stored at address 40000** ($9C40 in hex)
   - This is where the simulator reads memory for validation
   - This is the agreed-upon test address for Atari

2. **Memory dump configuration in .json**
   - Specify exactly which addresses to dump
   - Format: `"dump_memory": ["0x9C40-0x9C40"]` for single address

3. **File naming is critical**
   - Passing test: `tests/pass/NNN-name/NNN-name.{zap,s,json,ref,md}`
   - Error test: `tests/fail/NNN-name-error/NNN-name-error.{zap,ref,md}`

4. **Test code should be minimal but complete**
   - Test ONE feature per test
   - Store results at address 40000 for verification
   - Include descriptive comments in source

5. **.md files for descriptions**
   - Provides comprehensive test documentation
   - Won't be deleted by `make clean`
   - Can include sections: Purpose, Feature, Expected Behavior, Memory Validation

## Next Tests to Create

- [ ] 002-word-type (16-bit integer)
- [ ] 003-byte-pointers (pointer to byte)
- [ ] 004-word-pointers (pointer to word)
- [ ] 005-arrays-1d-byte (1D byte array)
- ... (38 more tests following same structure)

## Validation Process

User will:
1. Compile test: `make.bat tests` or `make tests`
2. Check memory dumps: Compare actual vs expected
3. Validate error messages: Check error tests catch errors
4. Review assembly: Inspect generated .s files if needed
5. Approve or request changes

---

**Status**: ✅ Tests 000 and 001 complete with correct structure  
**Ready for**: User review and validation of tests  
**Next Step**: Create test 002-word-type following same pattern
