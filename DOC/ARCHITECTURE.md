# ZAP! Transpiler Architecture Summary

Based on the analysis of the ZAP! to 6502/65c02 assembly transpiler codebase, here is the summary of its architecture, type representation, operator processing, and code generation mechanisms.

## Overall Architecture
The compiler (`compiler.py` and `compiler_pipeline.py`) follows a traditional multi-pass ahead-of-time (AOT) compilation pipeline:
1. **Preprocessing & Parsing**: Uses `preprocessor.py` for macros/includes and `parser.py` (a recursive descent parser) to generate an Abstract Syntax Tree (AST) defined in `ast_nodes.py`.
2. **Module System**: `module_system.py` handles includes and resolves dependencies between multiple source files (`.zap`).
3. **Semantic Analysis (Type Checking)**: Walk the AST using modules like `sema_proc.py`, `sema_func.py`, and `sema_expr.py` to enforce type rules, check defined symbols, and resolve structs.
4. **Optimization Passes**: Runs optimization routines like Dead Code Elimination (DCE in `dce.py`) based on an interference and liveness graph to prune unused procedures, functions, and variables.
5. **Code Generation**: Translates the checked AST into 6502 assembly strings in `codegen_expr.py` (and similar modules). 
6. **Post-processing**: Optional peephole optimization over generated assembly.

## Type Representation
Types in the compiler exist in multiple forms depending on the compilation phase:
- **`TypeNode` (in AST)**: Represents the syntactic type (e.g., `byte`, `word`) and whether it has a pointer modifier (`^`).
- **`SemType` (in `symbols.py`)**: The semantic type used during type checking. It stores the base name (e.g., "BYTE", "WORD", "LONG", or a structural name), a boolean `is_pointer`, and a boolean `is_struct` with an optional `StructInfo` metadata field.
- **`ExprType` (in `sema_types.py`)**: A wrapper around `SemType` for expressions that also specifies an `ExprKind` which flags the evaluation category:
  - `VALUE`: An r-value (read-only value, such as literals or temporary math results).
  - `LVALUE`: An assignable memory location (e.g., a variable, an array element).
  - `ADDR`: The address of something (e.g., of a pointer variable or an array reference).
- Complex types, such as `StructRegistry` and `Symbol` tables, map variable identifiers to these types, including arrays with multidimensional support (`array_dims`).

## Operator Processing
Operator processing and type matching are predominately handled in `sema_expr.py` via the `ExprTypeChecker` class:
- **Expression Validation**: Validates unary and binary expressions recursively.
- **LVALUE to VALUE Conversion**: If an `LVALUE` is used in a binary/unary operation (a read context), it checks hardware port restrictions and transparently degrades it to a `VALUE`.
- **Promotion & Casting**: The `promote(a: SemType, b: SemType)` function handles implicit coercion. For example, if either operand is `LONG`, the common type is `LONG`; if one is `WORD` or a pointer, it promotes to `WORD`; otherwise `BYTE`.
- **Restrictions on Types**: Specific restrictions are enforced. For example, `Struct` types cannot be used in arithmetic binary operations. Pointer arithmetic is constrained (e.g., addition allows only pointer + value). Bitwise and arithmetic operations require standard values.
- **Multi-dimension Arrays**: Resolves sequences of `SubscriptExpr`s. An intermediate subscript correctly yields an `ADDR` to the remaining array slice, while the final subscript resolves to the target `LVALUE`.

## Code Generation
Code generation (`codegen_expr.py`) converts typical AST nodes into 6502 assembly language specifically targeting ca65 format.
- **RPN Translation**: The AST expression trees are flattened. The `ast_to_rpn` function traverses binary/unary expression trees and converts them into Reverse Polish Notation (RPN), assigning type widths dynamically.
- **Virtual Accumulator & Hardware Registers**: 
  - The compiler tries to utilize the **A** and **X** registers for direct immediate mathematical operations (8-bit resides in A, 16-bit extends to X:A).
  - It detects simple operations that can bypass advanced stack manipulation using a "Fast Path Optimization" (e.g., a simple bit mask).
- **Zero Page Virtual Registers**: Operations surpassing simple registers dump parameters to virtual 16/32-bit zero-page registers: `MATH0`, `MATH1`, and `MATH_STACK` (an overflow pseudo-stack in zero page or variables).
- **Subroutines for Math**: Complex operations (like 16-bit multiplication `MUL16`, 32-bit division `DIV32`, bit shifts `LSHIFT32`) fall back to generated or pre-linked assembly routines (`JSR MUL16`), mitigating code bloat.

## Enum to CONST Architecture Design
Following a comprehensive optimization pass, Enum evaluation architecture was refactored:
- Enums members, parsed initially as `FieldAccess` descriptors, are securely transformed into compile-time standard `CONST` nodes.
- By intercepting early in the compilation stream (`constsubst.py`), any occurrences of Enum access are explicitly translated into standard `IntLiteral` occurrences, preventing traversal into the unoptimized RPN translation generator.
- This uniform behavior ensures `enum` variables flawlessly support complete algebraic and logical reduction mechanisms precisely analogous to standard numeric values or compile-time variable constants natively targeted for simple inline 6502 assignments.
