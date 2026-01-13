# Zap Compiler - Project State

**Date**: January 11, 2026  
**Repository**: Dushino/Action-transpiler (to be renamed)  
**Branch**: main

## Overview

Zap is a modern compiler for the Action! programming language targeting the Atari 8-bit platform and other 6502-based systems. The compiler features advanced optimizations including constant folding, dead code elimination, and algebraic simplification. It compiles Action! source code (.act files) into optimized 6502 assembly (.s files).

## Project Structure

### Core Compiler Components

#### Frontend (Lexical & Syntactic Analysis)
- **tokenizer.py** - Lexical analyzer that converts source text into tokens
- **token_types.py** - Token type definitions
- **lexer.py** - Additional lexing functionality
- **parser.py** - Recursive descent parser that builds an Abstract Syntax Tree (AST)
- **ast_nodes.py** - AST node definitions (Program, ProcDecl, FuncDecl, AssignStmt, Parameter, etc.)

#### Module System
- **module_system.py** - Handles .module and .include directives for multi-file compilation
  - Parses module/include directives
  - Loads and caches modules with dependency resolution
  - Detects circular dependencies
  - Merges symbol tables from included modules
  - Preserves include order for proper symbol visibility

#### Semantic Analysis
- **sema.py** - Main semantic analyzer entry point
- **sema_expr.py** - Expression type checking (ExprTypeChecker)
- **sema_proc.py** - Procedure semantic analysis (ProcAnalyzer)
- **sema_func.py** - Function semantic analysis (FuncAnalyzer)
- **sema_types.py** - Type system definitions
- **symbols.py** - Symbol table management (SymbolTable, ProcTable, FuncTable)
- **identifier.py** - Identifier handling

#### Optimization Passes
- **constfold.py** - Constant folding optimization
- **constsubst.py** - Constant substitution
- **dce.py** - Dead code elimination (removes unreachable code after break/continue/return)
- **jump_threading.py** - Jump threading optimization for assembly code
- **label_cleanup.py** - Removes unused labels from assembly code (handles JSR targets)

#### Code Generation
- **codegen_expr.py** - 6502 assembly code generator (CodeGen class)
- **compiler_pipeline.py** - Orchestrates the compilation pipeline

#### Error Handling
- **errors.py** - Error type definitions (SemanticError)

#### Main Entry Point
- **compiler.py** - Main compiler driver
  - `compile_source(src)` - Compiles source string
  - `compile_file(filepath)` - Compiles file with module support

### Support Files

#### Libraries & Configuration
- **lib/** - Assembly libraries and macros
  - macros.inc, macros.s - General purpose macros
  - atari/ - Atari-specific hardware definitions (ANTIC, GTIA, POKEY)
  - atari/exehdr.s - Executable header for Atari binaries
- **cfg/my_atari.cfg** - Linker configuration for Atari target

#### Documentation
- **DOC/grammar.ebnf** - Formal grammar definition in EBNF notation
- **DOC/setup_dev_env.txt** - Development environment setup instructions

#### Testing
- **tests/** - Test suite containing .act source files and expected .s assembly outputs
  - test_if_0.act / test_if_0.s - IF statement with constant false condition
  - test_if_1_else.act / test_if_1_else.s - IF-ELSE statement with constant true condition
  - test_while_0.act / test_while_0.s - WHILE loop with constant false condition
  - test_break_continue.act / test_break_continue.s - BREAK and CONTINUE statements
  - test_for_const_step.act / test_for_const_step.s - FOR loop with constant step
  - test_for_dynamic_step.act / test_for_dynamic_step.s - FOR loop with dynamic step
- **tests.bat** - Batch script to compile all test files

#### Build System
- **make.bat** - Windows build script
- **backup/** - Contains previous versions of core files

#### Sample Code
- **test.act** - Sample Action program
- **p1.s** - Generated assembly output
- **p1/** - Additional test programs

## Language Features

### Supported Language Constructs

Based on the grammar (DOC/grammar.ebnf):

#### Data Types
- **byte** - 8-bit unsigned integer
- **word** - 16-bit unsigned integer
- **char** - Character type
- Pointer types via `^` operator

#### Declarations
- Variable declarations with optional `const` qualifier
- Array declarations with `[]` syntax
- Address specifications
- Initializers

#### Module System
- `.module "filename.act"` - Marks a file as a module (can be included by others)
- `.include "filename.act"` - Includes another module's declarations, procedures, and functions
- Circular dependency detection
- Include guards (files are only included once)

#### Control Flow
- `IF-THEN-ELSE-ENDIF` conditional statements
- `WHILE-END` loops
- `FOR-TO-NEXT` loops with constant or dynamic step values
- `BREAK` statement
- `CONTINUE` statement
- `RETURN` statement (with expression for FUNC, without for PROC)

#### Procedures & Functions
- `PROC` declarations with parameters, ended with `END`
- `FUNC` declarations with typed return values, ended with `RETURN expr`
- Parameter passing (including array parameters via `[]`)
- Call arguments evaluated left-to-right

#### Expressions
- Arithmetic operators: `+`, `-`, `*`, `/`, `%`
- Comparison operators: `<`, `>`, `<=`, `>=`, `==`, `!=`
- Logical operators: `AND`, `OR`
- Unary operators: `-`, `!`
- Array indexing: `array[index]`
- Pointer dereferencing: `var^`
- Function calls with arguments
- Procedure calls (as statements)

## Compilation Pipeline

The compilation process follows these stages (as implemented in [compiler_pipeline.py](compiler_pipeline.py)):

1. **Module Loading** - Resolve includes and build complete program AST
2. **Tokenization** - Source text → Token stream
3. **Parsing** - Token stream → AST
4. **Symbol Table Construction** - Build global symbol table for variables
5. **Declaration Analysis** - Process all variable declarations
6. **Procedure/Function Registration** - Register all proc/func signatures
7. **Procedure/Function Analysis** - 
   - Analyze procedure/function bodies (statements, locals)
   - Type checking for expressions
8. **Dead Code Pruning** - 
   - Remove unreachable procedures/functions (not called from MAIN)
   - Remove unreachable globals (not referenced, except fixed-address)
   - Track referenced globals for initialization filtering
9. **Local Variable Pruning** - Remove unused local variables within each procedure/function
10. **Code Generation** - Generate 6502 assembly code
    - Globals initialization (only for referenced variables)
    - Procedure/function bodies
11. **Statement-Level DCE** - Remove unreachable statements after break/continue/return
12. **Peephole Optimization** - Apply peephole optimizations to generated assembly
13. **Variable Block Generation** - 
    - Detect used TMP temps via code scanning
    - Emit only used temps to zero-page
    - Allocate user variables with dynamic offset
14. **Assembly Optimization** - 
    - Jump threading (optimize jump chains)
    - Label cleanup (remove unused labels, preserve JSR targets)
    - Iteratively applied until no further changes

## Current Implementation Status

### ✅ Fully Implemented
- **Frontend**
  - Complete tokenizer/lexer
  - Parser for all core language constructs
  - Full AST representation
  
- **Semantic Analysis**
  - Symbol table management
  - Type checking for expressions
  - Procedure declaration and analysis
  - Function declaration and analysis
  - Global and local variable handling
  
- **Optimizations**
  - Constant folding (fold_expr)
  - Constant substitution (subst_const)
  - Dead code elimination (DCE):
    - Unreachable code after break/continue/return
    - Dead procedure/function pruning (removes unreachable procs/funcs from MAIN)
    - Dead local variable pruning (removes unused locals within procedures/functions)
    - **Dead global pruning with smart initialization** (removes unused globals AND their init code)
  - Assembly-level jump threading
  - Assembly-level label cleanup (preserves exports, immediates, JSR targets)
  - **Runtime library optimization**:
    - Math routines (MUL8/16, DIV8/16, MOD8/16) emitted only when used
    - Copy bytes routine emitted only when needed (string/array init)
  - **Zero-page temp optimization**:
    - TMP0-TMP4 variables allocated only when detected in generated code
    - Zero-page offset recomputed dynamically based on emitted temps
    - Unused temps eliminated, reclaiming valuable ZP space
  - **String initialization optimization**:
    - Short strings (≤2 chars): Inline initialization for speed
    - Long strings (≥3 chars): Loop-based copy from ROM data (64% code reduction)
    - String literals stored once in CODE segment
  - **Array initialization optimization**:
    - Short arrays (≤2 elements): Inline initialization for speed  
    - Long arrays (≥3 elements): Loop-based copy from ROM data (40% code reduction)
    - Constant arrays stored once in CODE segment
    - Supports both BYTE and WORD arrays
  
- **Code Generation - Variables & Initialization**
  - Variable declarations (byte, word)
  - Variable initialization with expressions
  - **Fixed-address variables** (hardware registers, memory-mapped I/O with `@address`)
    - Supports both globals and locals with explicit addresses
    - Fixed-address variables excluded from zero-page allocation
    - Always preserved regardless of usage
  - Array declarations with initializer lists (optimized)
  - String initialization (optimized with copy loops)
  - Atari-specific setup and headers
  - **Smart zero-page allocation**:
    - Pointers always in ZP (fail if exhausted)
    - BYTE/WORD variables fill ZP then overflow to BSS
    - Arrays always in BSS
    - Dynamic offset computation based on emitted temps
  
- **Code Generation - Expressions**
  - Binary arithmetic operators: +, -, *, /, %
    - Addition/Subtraction: Inline code for 8-bit and 16-bit operations
    - Multiplication: Runtime routines (MUL8, MUL16_8, MUL16) for all 8/16-bit combinations
    - Division: Runtime routines (DIV8, DIV16_8, DIV8_16, DIV16) for all 8/16-bit combinations
    - Modulo: Runtime routines (MOD8, MOD16_8, MOD8_16, MOD16) for all 8/16-bit combinations
  - Relational operators: ==, !=, <, >, <=, >=
  - Logical operators: &&, || (short-circuit evaluation)
  - Unary operators: -, !
  - Integer literals (decimal, hex 0x, binary %)
  - Character literals: `'x'` tokens as ASCII numbers (supports escapes: `\n`, `\t`, `\r`, `\"`, `\'`, `\\`)
  - Variable references (identifiers)
  - Pointer dereferencing (^)
  - Array indexing
  - Function calls in expressions with arguments
  
- **Code Generation - Control Flow**
  - IF-THEN-ELSE-ENDIF statements
  - WHILE-END loops
  - FOR-TO-NEXT loops (both constant and dynamic step)
  - BREAK statements
  - CONTINUE statements
  - RETURN statements
  
- **Code Generation - Procedures**
  - Procedure declarations
  - Procedure calls (CallStmt)
  - Local variables in procedures
  - Procedure body generation

- **Assembly Optimization & Peephole**
  - Illegal opcode detection and replacement (e.g., `ORA X` → `STX TMP4; ORA TMP4`)
  - Consecutive label merging
  - Dead label elimination (preserves exports, immediates, JSR targets)
  - Jump threading for label chains
  - ca65-compatible output (no `+` local labels, proper `.export` directives)

### 🚧 Partial / In Progress
- **Functions**
  - Function declarations and signatures (analyzed)
  - Function body generation (gen_func exists)
  - Function return values
  - Integration with full pipeline

- **Advanced Features**
  - Pointer operations (partial)
  - Array operations (basic indexing works)
  - Multi-dimensional arrays
  - String handling

### 📝 Testing Status
- Comprehensive test suite with source (.act) and expected assembly (.s) pairs
- Tests cover: IF statements, WHILE loops, FOR loops, BREAK/CONTINUE
- Automated test compilation via tests.bat
- Focus on edge cases (constant conditions, dead code elimination)

## Build & Usage

### Compiling an Action Program
```batch
python compiler.py source.act > output.s
```

### Running All Tests
```batch
tests.bat
```
This compiles all .act files in the tests/ directory and generates corresponding .s files.

### Build Script
```batch
make.bat
```
Windows-specific build script for project setup.

## Target Platform

**Atari 8-bit Computer**
- CPU: MOS 6502
- Memory: 64KB addressable space
- Hardware: ANTIC (display), GTIA (graphics), POKEY (audio/I/O)

## Dependencies

- **Python 3.x** - Required for running the compiler
- **Standard Library Only** - No external Python packages required
- **CC65 Toolchain** (for final assembly/linking) - ca65/ld65 for Atari target
  - Used to assemble .s files to executable binaries
  - Configuration in cfg/my_atari.cfg

## Notes

- UTF-8 BOM handling is implemented in [compiler.py](compiler.py)
- The [backup/](backup/) folder contains older implementations for reference
- Configuration files support linking with CC65 toolchain (ca65/ld65)
- Assembly optimization passes run iteratively until convergence
- Dead code elimination removes statements after unconditional jumps (break/continue/return)
- Loop handling maintains a stack for nested BREAK/CONTINUE resolution
- FOR loops support both constant and dynamic step values with different code generation strategies

## Recent Improvements (January 2026)

1. ✅ **Fixed preprocessor directive handling** - Removed obsolete `#` directives from tokenizer
2. ✅ **CLI enhancement** - Added `-o` output option for file output
3. ✅ **Illegal opcode fixes** - Replaced invalid `ORA X` with safe sequence using TMP4
4. ✅ **ca65 compatibility** - Fixed label syntax (removed `+` local labels, proper exports)
5. ✅ **CODE segment organization** - Moved shared routines/data into CODE segment
6. ✅ **Export/import resolution** - Added `__END` label export, MAIN import in Atari header
7. ✅ **Zero-page optimization** - Fixed ZP allocation ordering (vars before CODE to resolve forward refs)
8. ✅ **Fixed-address locals** - Emit local variables with explicit addresses (`@`)
9. ✅ **Math runtime optimization** - Conditionally emit math routines only when mul/div/mod used
10. ✅ **Dead global elimination** - Remove unused global variables AND their initialization code
11. ✅ **TMP variable optimization** - Emit only used TMP0-TMP4 temps, reclaim unused ZP space

## Next Steps (Potential)

1. ✅ ~~Complete control flow code generation~~ (DONE)
2. ✅ ~~Dead code elimination~~ (DONE - procs/funcs/locals/globals/statements)
3. ✅ ~~Math runtime optimization~~ (DONE - conditional emission)
4. ✅ ~~Zero-page temp optimization~~ (DONE - usage-based allocation)
5. Complete function implementation and integration
6. Add more comprehensive error messages and source location tracking
7. Implement remaining pointer operations
8. Add string literal support improvements
9. Expand array functionality (multi-dimensional arrays)
10. Add more example programs and documentation
11. Optimize register allocation in expressions
12. Add unit tests with Python test framework
13. Performance profiling and optimization of generated assembly
