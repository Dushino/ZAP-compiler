# ZAP Language Features - Comprehensive Test Checklist

**Date**: January 20, 2026  
**Purpose**: Complete checklist of all ZAP language features for extensible test suite  
**Status**: Planning Phase

## Overview

This checklist covers ALL ZAP language features with all combinations and edge cases. 

### Test Structure
- **Passing Tests**: Each feature has a corresponding test in `./tests/pass/NNN-feature-name/`
- **Error Tests**: Each feature category has corresponding error tests in `./tests/fail/NNN-feature-name-error/`
  - Validates error detection and reporting
  - Ensures error messages are human-readable
  - Checks line number accuracy

### Checkbox Legend
- `[ ]` = Not yet tested
- `[✓]` = Pass test created (in `./tests/pass/`)
- `[!]` = Error test created (in `./tests/fail/`)

---

## 1. DATA TYPES & DECLARATIONS

### Basic Types
- [ ] BYTE type declaration and usage
- [ ] WORD type declaration and usage
- [ ] Byte pointer (byte ^) declaration
- [ ] Word pointer (word ^) declaration
- [ ] Multi-level pointers (byte ^^)

### Variable Declarations
- [ ] Global BYTE variable
- [ ] Global WORD variable
- [ ] Global byte pointer
- [ ] Global word pointer
- [ ] Local BYTE variable
- [ ] Local WORD variable
- [ ] Local byte pointer
- [ ] Local word pointer
- [ ] Variable initialization with literal values
- [ ] Variable initialization with expressions
- [ ] Multiple variables in single declaration

### Constants
- [ ] Const BYTE scalar
- [ ] Const WORD scalar
- [ ] Const byte pointer
- [ ] Const word pointer
- [ ] Const array of BYTE
- [ ] Const array of WORD
- [ ] Const struct
- [ ] Const complex expressions
- [ ] Const address values (@variable)

---

## 2. ARRAYS

### 1D Arrays
- [ ] BYTE array with explicit size
- [ ] WORD array with explicit size
- [ ] BYTE pointer array
- [ ] WORD pointer array
- [ ] Array with inferred size from initializer
- [ ] Array with list initialization
- [ ] Array with string initialization (byte arrays only)
- [ ] Array subscript access (read)
- [ ] Array subscript access (write)
- [ ] Array subscript in expressions
- [ ] Array element with operators

### Multi-Dimensional Arrays (2D)
- [ ] 2D BYTE array [3][4]
- [ ] 2D WORD array [2][3]
- [ ] 2D struct array
- [ ] 2D pointer array
- [ ] 2D array subscripting [i][j]
- [ ] 2D array nested initialization
- [ ] 2D array partial subscripting (returns pointer)

### Multi-Dimensional Arrays (3D+)
- [ ] 3D BYTE array [2][3][4]
- [ ] 3D WORD array [2][2][2]
- [ ] 3D array subscripting [i][j][k]
- [ ] 3D array initialization
- [ ] 4D+ array support

### Array Edge Cases
- [ ] Array with size 1
- [ ] Large arrays (100+ elements)
- [ ] Nested array access in expressions
- [ ] Array bounds in loops

---

## 3. POINTERS & DEREFERENCING

### Pointer Declaration & Initialization
- [ ] Byte pointer to global variable
- [ ] Byte pointer to local variable
- [ ] Word pointer to global variable
- [ ] Word pointer to local variable
- [ ] Pointer initialization with address (@)
- [ ] Pointer initialization with literal address
- [ ] Pointer to array element

### Pointer Dereference
- [ ] Byte pointer dereference (read)
- [ ] Byte pointer dereference (write)
- [ ] Word pointer dereference (read)
- [ ] Word pointer dereference (write)
- [ ] Pointer dereference in expressions
- [ ] Pointer dereference on both sides of assignment
- [ ] Multi-level pointer dereference (^^)

### Pointer Arithmetic
- [ ] Byte pointer + integer
- [ ] Byte pointer - integer
- [ ] Word pointer + integer (stride by 2)
- [ ] Word pointer - integer (stride by 2)
- [ ] Pointer arithmetic in loops
- [ ] Pointer arithmetic with array iteration
- [ ] Pointer to struct element arithmetic

### Address-of Operator
- [ ] Address of global variable
- [ ] Address of local variable
- [ ] Address of array element
- [ ] Address of struct field
- [ ] Address of function
- [ ] Address-of in initialization
- [ ] Address-of in expressions

---

## 4. STRUCTS

### Struct Declaration
- [ ] Simple struct with BYTE fields
- [ ] Struct with WORD fields
- [ ] Struct with mixed BYTE/WORD fields
- [ ] Struct with pointer fields
- [ ] Struct with array fields
- [ ] Nested struct (struct containing struct)
- [ ] Recursive struct reference

### Struct Variables
- [ ] Global struct variable
- [ ] Local struct variable
- [ ] Struct parameter in function
- [ ] Struct return from function
- [ ] Struct with initialization
- [ ] Const struct variable
- [ ] Volatile struct (if applicable)

### Struct Field Access
- [ ] Simple field access (read)
- [ ] Simple field access (write)
- [ ] Nested field access (struct.field1.field2)
- [ ] Field access in expressions
- [ ] Field access with pointer dereference
- [ ] Field access in arrays of structs

### Struct Arrays
- [ ] Array of simple structs
- [ ] Array of nested structs
- [ ] 2D array of structs
- [ ] Struct array element access
- [ ] Struct array field access
- [ ] Struct array initialization

### Struct Pointers
- [ ] Pointer to global struct
- [ ] Pointer to local struct
- [ ] Struct pointer dereference
- [ ] Struct pointer field access
- [ ] Pointer arithmetic on struct arrays

---

## 5. PROCEDURES & FUNCTIONS

### Procedure Declaration
- [ ] Procedure with no parameters
- [ ] Procedure with BYTE parameter
- [ ] Procedure with WORD parameter
- [ ] Procedure with pointer parameter (byte ^)
- [ ] Procedure with pointer parameter (word ^)
- [ ] Procedure with struct parameter
- [ ] Procedure with multiple parameters
- [ ] Procedure with array parameter

### Function Declaration
- [ ] Function returning BYTE
- [ ] Function returning WORD
- [ ] Function returning pointer (byte ^)
- [ ] Function returning pointer (word ^)
- [ ] Function returning struct
- [ ] Function with no parameters
- [ ] Function with multiple parameters
- [ ] Function parameter combinations

### Procedure/Function Calls
- [ ] Call with no arguments
- [ ] Call with BYTE argument
- [ ] Call with WORD argument
- [ ] Call with pointer argument
- [ ] Call with struct argument
- [ ] Call in expression context
- [ ] Call as statement
- [ ] Nested function calls
- [ ] Recursive function calls

### Local Variables
- [ ] Local BYTE variable
- [ ] Local WORD variable
- [ ] Local pointer
- [ ] Local struct
- [ ] Local array
- [ ] Multiple local variables
- [ ] Local variable shadowing (same name as global)
- [ ] Local variable scope boundaries

### Return Values
- [ ] Return BYTE literal
- [ ] Return WORD literal
- [ ] Return pointer
- [ ] Return struct
- [ ] Return expression result
- [ ] Return variable value
- [ ] Multiple return statements in function

---

## 6. CONTROL FLOW

### If-Then-Else
- [ ] Simple if statement
- [ ] If-else statement
- [ ] If with no braces (single statement)
- [ ] If-else with no braces
- [ ] Nested if statements
- [ ] If with complex condition
- [ ] If with comparison operators
- [ ] If with logical operators

### While Loops
- [ ] Simple while loop
- [ ] While with counter variable
- [ ] While with pointer arithmetic
- [ ] Nested while loops
- [ ] While with break statement
- [ ] While with continue statement
- [ ] While with empty body
- [ ] While with complex condition

### For Loops
- [ ] Simple for loop with counter
- [ ] For loop with array iteration
- [ ] Nested for loops
- [ ] For loop with break
- [ ] For loop with continue
- [ ] For loop with modification in loop
- [ ] For loop with complex init/update
- [ ] For loop over 2D array

### Break & Continue
- [ ] Break in while loop
- [ ] Break in for loop
- [ ] Break in nested loop
- [ ] Continue in while loop
- [ ] Continue in for loop
- [ ] Continue in nested loop

---

## 7. OPERATORS & EXPRESSIONS

### Arithmetic Operators
- [ ] Addition (+)
- [ ] Subtraction (-)
- [ ] Multiplication (*)
- [ ] Division (/)
- [ ] Modulo (%)
- [ ] Unary minus (-)
- [ ] Operator precedence (mixed operators)

### Bitwise Operators
- [ ] Bitwise AND (&)
- [ ] Bitwise OR (|)
- [ ] Bitwise XOR (^)
- [ ] Bitwise NOT (~)
- [ ] Left shift (<<)
- [ ] Right shift (>>)
- [ ] Bitwise operators in expressions

### Comparison Operators
- [ ] Equal (==)
- [ ] Not equal (!=)
- [ ] Less than (<)
- [ ] Greater than (>)
- [ ] Less than or equal (<=)
- [ ] Greater than or equal (>=)
- [ ] Comparison chaining (a < b < c?)

### Logical Operators
- [ ] Logical AND (&&)
- [ ] Logical OR (||)
- [ ] Logical NOT (!)
- [ ] Short-circuit evaluation
- [ ] Mixed logical operators

### Assignment & Compound Assignment
- [ ] Simple assignment (=)
- [ ] += (add and assign)
- [ ] -= (subtract and assign)
- [ ] *= (multiply and assign)
- [ ] /= (divide and assign)
- [ ] %= (modulo and assign)
- [ ] &= (bitwise AND and assign)
- [ ] |= (bitwise OR and assign)
- [ ] ^= (bitwise XOR and assign)
- [ ] <<= (shift left and assign)
- [ ] >>= (shift right and assign)

### Expression Context
- [ ] Complex expressions
- [ ] Operator precedence
- [ ] Parentheses override precedence
- [ ] Assignment in expression
- [ ] Multiple operators in single expression

---

## 8. STRINGS & ESCAPE SEQUENCES

### String Literals
- [ ] Simple ASCII string
- [ ] String with spaces
- [ ] Empty string
- [ ] String with special characters
- [ ] String assignment to byte array
- [ ] String in initialization

### Escape Sequences
- [ ] \\n (newline)
- [ ] \\r (carriage return)
- [ ] \\t (tab)
- [ ] \\\\ (backslash)
- [ ] \\" (quote)
- [ ] \\x (hex escape)
- [ ] \\0 Octal escapes

### String in Arrays
- [ ] Byte array from string
- [ ] String with inferred size
- [ ] String with explicit size
- [ ] String initialization

---

## 9. COMMENTS & SOURCE METADATA

### Comments
- [ ] Single-line comment (;)
- [ ] Multiple single-line comments
- [ ] Comments between statements
- [ ] Comments on same line as code
- [ ] Nested comment-like content

### Source Line Tracking
- [ ] Proper line number in errors
- [ ] Multiple statements per line
- [ ] Long lines
- [ ] Multiline expressions (if supported)

---

## 10. INITIALIZATION PATTERNS

### Scalar Initialization
- [ ] Zero initialization
- [ ] Literal value initialization
- [ ] Expression initialization
- [ ] Address-of initialization

### Array Initialization
- [ ] Empty list initialization
- [ ] Full list initialization
- [ ] Partial list initialization (shorter than array)
- [ ] Nested list (2D/3D arrays)
- [ ] String initialization
- [ ] Inferred size from initializer

### Struct Initialization
- [ ] Struct with field order
- [ ] Struct with nested structs
- [ ] Struct in array
- [ ] Struct with pointer fields

---

## 11. SPECIAL FEATURES

### Fixed Address Variables (@address)
- [ ] Variable at fixed memory address
- [ ] Accessing fixed address memory
- [ ] Writing to fixed address
- [ ] Fixed address in different ranges

### Const Enforcement
- [ ] Const variable cannot be modified
- [ ] Const array behavior
- [ ] Const struct behavior

### Volatile Variables (if supported)
- [ ] Volatile variable declaration
- [ ] Volatile read behavior
- [ ] Volatile write behavior

### Module System (if supported)
- [ ] Include/import statement
- [ ] External function declaration
- [ ] Public/private scope

---

## 12. ERROR CASES & EDGE CASES

### Type Mismatches
- [ ] BYTE to WORD implicit conversion
- [ ] Pointer type mismatches
- [ ] Struct type mismatches

### Array Bounds (compile-time detection)
- [ ] Array size validation
- [ ] Multi-dimensional size validation

### Undefined Behavior (graceful handling)
- [ ] Uninitialized variable use
- [ ] Pointer to out-of-scope variable
- [ ] Recursive data structures

### Naming & Scope
- [ ] Duplicate global definitions
- [ ] Duplicate local definitions
- [ ] Shadowing (local hides global)
- [ ] Forward declarations

---

## 13. COMPLETE INTEGRATION TESTS

### Complex Programs
- [ ] Matrix operations (2D array processing)
- [ ] Linked data structure (pointer chains)
- [ ] Mixed struct and array usage
- [ ] Deep nesting (procedures calling procedures)
- [ ] Large program with all features

---

## Test Organization

Tests will be organized as:
```
./tests/pass/
├── NNN-feature-name/
│   ├── source.zap        (ZAP source code)
│   ├── source.ref        (expected memory dump)
│   └── description.txt   (test description)
└── ...
```

## Statistics

- **Total Feature Categories**: 13
- **Total Checkboxes**: ~200+ individual test cases
- **Estimated Tests**: 100-150 individual test files

## Status

| Phase | Status | Description |
|-------|--------|-------------|
| Planning | ✅ COMPLETE | Checklist created with all features |
| Directory Setup | ⏳ TODO | Create subdirectories in ./tests/pass |
| Test Creation | ⏳ TODO | Create .zap and .ref files for each test |
| Validation | ⏳ TODO | Verify each test passes correctly |
| Documentation | ⏳ TODO | Document test execution and results |

---

**Next Steps**:
1. Review this checklist for completeness
2. Create subdirectories in ./tests/pass for each test
3. Begin creating individual test files
4. Validate each test with reference output
