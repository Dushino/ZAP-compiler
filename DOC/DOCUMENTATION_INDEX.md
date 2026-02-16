# ZAP! Language Documentation Hub

**Complete Documentation for the ZAP! Programming Language**

**Latest Update**: January 19, 2026  
**Version**: 1.0

---

## Quick Navigation

### 🚀 I'm New to ZAP!
Start here if you're just beginning:

1. **[Getting Started Guide](GETTING_STARTED.md)** ⭐ **START HERE**
   - Installation and setup
   - Your first ZAP program
   - Basic variables and control flow
   - Functions and procedures
   - Arrays and strings

### 📚 I Need Complete Language Reference

2. **[ZAP! Language Reference Manual](ZAP_LANGUAGE_REFERENCE.md)** - Full Documentation
   - Data types (byte, word, pointers)
   - Variables and scope
   - All operators
   - Control flow structures
   - Procedures and functions
   - Arrays and strings
   - Pointers and memory
   - Module system
   - Atari-specific features

### 🧠 I'm Ready for Advanced Topics

3. **[Advanced Programming Topics](ADVANCED_TOPICS.md)** - Expert Techniques
   - Deep pointer operations
   - Memory management and zero-page allocation
   - Inline assembly integration
   - **Assembly label naming convention** (`_` for source, `__` for compiler-generated)
   - Hardware register access
   - Optimization techniques
   - Module system deep dive
   - Performance profiling
   - Advanced design patterns
   - Debugging assembly output

### 📖 Technical References

4. **[Grammar Definition (EBNF)](grammar.ebnf)** - Formal Syntax
   - Complete BNF grammar
   - Token definitions
   - Operator precedence
   - Language structure

5. **[PORT Modifier Implementation](PORT_MODIFIER_IMPLEMENTATION.md)** - Details about `#PORT`, `#RD`, and `#WR` modifiers for hardware ports
   - Syntax, semantics, restrictions, and examples

6. **[Symbol Naming Quick Reference](SYMBOL_NAMING_QUICK_REFERENCE.md)** ⚡ **CHEAT SHEET**
   - Assembly label name mangling rules
   - `_` prefix for source identifiers (variables, procedures, functions)
   - `__` prefix for compiler-generated symbols
   - Quick lookup tables for all symbol types
   - Common usage patterns and examples
   - Debugging tips

7. **[Uninitialized Variable Detection](UNINITIALIZED_VARIABLE_DETECTION.md)** - Compile-Time Safety
   - Definite-assignment analysis
   - Control flow handling (IF, WHILE, REPEAT, SWITCH)
   - Special cases (const, structs, parameters, address-of)
   - Error messages and best practices
   - Limitations and workarounds

8. **[Function Calls as Statements](FUNCTION_CALLS_AS_STATEMENTS.md)** - Language Feature
   - Call functions without capturing return values
   - Syntax, semantics, and code generation
   - Use cases and design patterns
   - Comparison with procedures

9. **[Project State & Implementation](project_state.md)** - Compiler Details
   - Architecture overview
   - Compilation pipeline
   - Implementation status
   - Optimization details
   - Testing framework
   - Known limitations

10. **[Advanced Notes & Internals](advanced_notes.md)** - Implementation Deep Dive
   - Internal identifier naming
   - Memory layout strategies
   - Variable scope rules
   - Static local variables
   - Assembler considerations

11. **[Quick Reference](QUICK_REFERENCE.md)** - At-a-Glance Syntax
   - Concise syntax summary
   - Common patterns
   - Quick lookup

---

## Learning Path

### Beginner (Start Here)

**Goal**: Write your first working ZAP program

**Steps**:
1. Read: [Getting Started - What is ZAP?](GETTING_STARTED.md#what-is-zap)
2. Read: [Getting Started - Installation](GETTING_STARTED.md#installation)
3. Read: [Getting Started - Your First Program](GETTING_STARTED.md#your-first-program)
4. **Practice**: Write a simple variable initialization program
5. Read: [Getting Started - Variables](GETTING_STARTED.md#working-with-variables)
6. **Practice**: Create a program with multiple variables

**Time**: 30-60 minutes

### Beginner to Intermediate

**Goal**: Understand control flow and write non-trivial programs

**Steps**:
1. Read: [Language Reference - Control Flow](ZAP_LANGUAGE_REFERENCE.md#control-flow)
2. Read: [Getting Started - Making Decisions](GETTING_STARTED.md#making-decisions)
3. Read: [Getting Started - Loops](GETTING_STARTED.md#loops)
4. **Practice**: Write program with if/else logic
5. **Practice**: Write program with loops
6. Read: [Language Reference - Procedures & Functions](ZAP_LANGUAGE_REFERENCE.md#procedures--functions)
7. **Practice**: Create programs with procedures and functions

**Time**: 2-3 hours

### Intermediate

**Goal**: Master arrays, strings, and create real projects

**Steps**:
1. Read: [Language Reference - Arrays & Strings](ZAP_LANGUAGE_REFERENCE.md#arrays--strings)
2. Read: [Getting Started - Arrays](GETTING_STARTED.md#arrays)
3. **Practice**: Array initialization and manipulation
4. Read: [Language Reference - Pointers](ZAP_LANGUAGE_REFERENCE.md#pointers)
5. **Practice**: Simple pointer operations
6. Read: [Language Reference - Module System](ZAP_LANGUAGE_REFERENCE.md#module-system)
7. **Practice**: Create multi-file programs

**Time**: 4-6 hours

### Intermediate to Advanced

**Goal**: Optimize code and use advanced features

**Steps**:
1. Read: [Advanced Topics - Pointer Operations](ADVANCED_TOPICS.md#pointer-operations)
2. Read: [Advanced Topics - Memory Management](ADVANCED_TOPICS.md#memory-management)
3. Read: [Advanced Topics - Inline Assembly](ADVANCED_TOPICS.md#inline-assembly)
4. **Important**: [Symbol Naming Quick Reference](SYMBOL_NAMING_QUICK_REFERENCE.md) - Essential for inline assembly!
5. Read: [Advanced Topics - Hardware Access](ADVANCED_TOPICS.md#hardware-access)
6. **Practice**: Write hardware-aware programs
7. Read: [Project State - Optimization Details](project_state.md#current-implementation-status)

**Time**: 6-8 hours

### Advanced

**Goal**: Master optimization and create professional software

**Steps**:
1. Read: [Advanced Topics - Optimization Techniques](ADVANCED_TOPICS.md#optimization-techniques)
2. Read: [Advanced Topics - Performance Profiling](ADVANCED_TOPICS.md#performance-profiling)
3. Read: [Advanced Topics - Advanced Patterns](ADVANCED_TOPICS.md#advanced-patterns)
4. Read: [Advanced Topics - Debugging Assembly](ADVANCED_TOPICS.md#debugging-assembly-output)
5. Read: [Project State - Compiler Internals](project_state.md#compilation-pipeline)
6. **Practice**: Profile and optimize real applications

**Time**: Ongoing

---

## By Topic

### Data & Types
- [Variables](ZAP_LANGUAGE_REFERENCE.md#variables)
- [Data Types](ZAP_LANGUAGE_REFERENCE.md#data-types)
- [Arrays & Strings](ZAP_LANGUAGE_REFERENCE.md#arrays--strings)
- [Pointers](ZAP_LANGUAGE_REFERENCE.md#pointers)
- [Memory Management](ADVANCED_TOPICS.md#memory-management)

### Control Flow
- [if-then-else](ZAP_LANGUAGE_REFERENCE.md#if-then-else-statement)
- [while Loops](ZAP_LANGUAGE_REFERENCE.md#while-loop)
- [for Loops](ZAP_LANGUAGE_REFERENCE.md#for-loop)
- [break Statement](ZAP_LANGUAGE_REFERENCE.md#break-statement)
- [Zero/Non-Zero Evaluation](ZAP_LANGUAGE_REFERENCE.md#zeronon-zero-evaluation)

### Functions & Procedures
- [Procedures](ZAP_LANGUAGE_REFERENCE.md#procedures)
- [Functions](ZAP_LANGUAGE_REFERENCE.md#functions)
- [Parameters](ZAP_LANGUAGE_REFERENCE.md#parameters)
- [Local Variables](ZAP_LANGUAGE_REFERENCE.md#local-variables)
- [Return Statements](ZAP_LANGUAGE_REFERENCE.md#return-statement)
- [Function Calls as Statements](FUNCTION_CALLS_AS_STATEMENTS.md) - Call functions without capturing return value

### Operators
- [Arithmetic](ZAP_LANGUAGE_REFERENCE.md#arithmetic-operators)
- [Comparison](ZAP_LANGUAGE_REFERENCE.md#comparison-operators)
- [Logical](ZAP_LANGUAGE_REFERENCE.md#logical-operators)
- [Unary Operators](ZAP_LANGUAGE_REFERENCE.md#unary-operators)
- [Operator Precedence](ZAP_LANGUAGE_REFERENCE.md#operator-precedence)

### Advanced Programming
- [Pointer Operations](ADVANCED_TOPICS.md#pointer-operations)
- [Inline Assembly](ADVANCED_TOPICS.md#inline-assembly)
- [Hardware Access](ADVANCED_TOPICS.md#hardware-access)
- [Optimization](ADVANCED_TOPICS.md#optimization-techniques)
- [State Machines](ADVANCED_TOPICS.md#state-machine)
- [Object Pooling](ADVANCED_TOPICS.md#object-pooling)

### Module System
- [Modules Basics](ZAP_LANGUAGE_REFERENCE.md#module-system)
- [Module Deep Dive](ADVANCED_TOPICS.md#module-system-deep-dive)
- [Organization](ADVANCED_TOPICS.md#include-organization)
- Module constructors support (see Module System docs)

### Compilation & Tools
- [Build Process](ZAP_LANGUAGE_REFERENCE.md#compilation-and-linking)
- [Compiler Pipeline](project_state.md#compilation-pipeline)
- [Optimization Levels](ADVANCED_TOPICS.md#compiler-optimizations)
- [Debugging Output](ADVANCED_TOPICS.md#debugging-assembly-output)

### Atari-Specific
- [Hardware Registers](ADVANCED_TOPICS.md#atari-8-bit-registers)
- [Memory Map](ZAP_LANGUAGE_REFERENCE.md#atari-specific-features)
- [Atari Features](ZAP_LANGUAGE_REFERENCE.md#atari-specific-features)

---

## Quick Reference Tables

### Data Types

| Type | Range | Size | Common Use |
|------|-------|------|-----------|
| `byte` | 0-255 | 1 byte | Small numbers, flags, coordinates |
| `word` | 0-65535 | 2 bytes | Addresses, large counts |
| `byte ^` | Any | 2 bytes (address) | Pointer to byte data |
| `word ^` | Any | 2 bytes (address) | Pointer to word data |

### Operators

| Category | Operators | Precedence |
|----------|-----------|-----------|
| Logical OR | `\|\|` | Lowest |
| Logical AND | `&&` | |
| Equality | `==`, `!=` | |
| Comparison | `<`, `>`, `<=`, `>=` | |
| Addition/Subtraction | `+`, `-` | |
| Multiplication/Division | `*`, `/`, `%` | |
| Unary | `-`, `!` | Highest |

### Keywords

| Category | Keywords |
|----------|----------|
| Procedures | `proc`, `end` |
| Functions | `func`, `return`, `end` |
| Control Flow | `if`, `then`, `else`, `endif` |
| Loops | `while`, `for`, `to`, `step`, `end`, `break` |
| Types | `byte`, `word` |
| Modifiers | `const`, `#KEEP`, `#NOEXPORT`, `#EXPORT` |
| Directives | `.module`, `.include`, `.error`, `.warning`, `.info` |
| Assembly | `asm`, `end` |

---

## Common Questions

### Q: Where should I start?
**A:** Begin with the [Getting Started Guide](GETTING_STARTED.md). It covers installation and your first program.

### Q: What's the difference between proc and func?
**A:** `proc` doesn't return a value, `func` does. See [Procedures & Functions](ZAP_LANGUAGE_REFERENCE.md#procedures--functions).

### Q: How do I access hardware registers?
**A:** Use fixed-address variables. See [Hardware Access](ADVANCED_TOPICS.md#hardware-access).

### Q: How do pointers work?
**A:** See [Pointers](ZAP_LANGUAGE_REFERENCE.md#pointers) for basics, or [Advanced Pointer Operations](ADVANCED_TOPICS.md#pointer-operations) for details.

### Q: Can I use assembly code?
**A:** Yes! Use `asm ... end` blocks. See [Inline Assembly](ADVANCED_TOPICS.md#inline-assembly) and [Symbol Naming Quick Reference](SYMBOL_NAMING_QUICK_REFERENCE.md) for name mangling rules.

### Q: How do I optimize my code?
**A:** Read [Optimization Techniques](ADVANCED_TOPICS.md#optimization-techniques) and [Performance Profiling](ADVANCED_TOPICS.md#performance-profiling).

### Q: How do I split code into multiple files?
**A:** Use the module system with `.module` and `.include`. See [Module System](ZAP_LANGUAGE_REFERENCE.md#module-system).

### Q: What's the memory layout?
**A:** See [Memory Management](ADVANCED_TOPICS.md#memory-management) and [Advanced Notes](advanced_notes.md).

### Q: How do I debug my program?
**A:** Check generated assembly and use comments. See [Debugging](ADVANCED_TOPICS.md#debugging-assembly-output).

### Q: Where can I find examples?
**A:** Check the `tests/pass/` directory in the repository for working examples.

---

## Documentation Structure

```
DOC/
├── README.md                           (Quick intro)
├── DOCUMENTATION_INDEX.md              (This file)
├── GETTING_STARTED.md                  ⭐ Start here for beginners
├── ZAP_LANGUAGE_REFERENCE.md          Complete language reference
├── ADVANCED_TOPICS.md                  Advanced programming
├── grammar.ebnf                        Formal grammar
├── project_state.md                    Implementation status
├── advanced_notes.md                   Implementation details
├── QUICK_REFERENCE.md                  Quick syntax lookup
├── VSCODE_INTEGRATION.md               VS Code setup
├── MODULE_SYSTEM.md                    Module system details
├── POINTER_ARITHMETIC.md               Pointer operations
├── NON_ZP_POINTERS_SUMMARY.md          Non-zero-page pointers
└── fix_deref_in_expressions.md         Expression improvements
```

---

## Key Concepts at a Glance

### Variables
```zap
byte x = 5          ; 8-bit variable
word y = 1000       ; 16-bit variable
byte ^ptr           ; Pointer to byte
```

### Control Flow
```zap
if condition then ... endif             ; Conditional
while condition ... end                 ; Loop
for i = 0 to 10 ... end                 ; Counter loop
```

### Procedures & Functions
```zap
proc name() ... end                     ; Procedure
func byte name() ... return value end   ; Function
```

### Arrays & Strings
```zap
byte arr[10]                            ; Array
byte msg[] = "Hello"                    ; String
byte value = arr[0]                     ; Access
```

### Pointers
```zap
byte x = 42
byte ^ptr = ^x                          ; Get address
byte val = ptr^                         ; Dereference
ptr = ptr + 1                           ; Arithmetic
```

### Modules
```zap
.module "name"                          ; Declare module
.include "file.zaplib"                  ; Include module
```

---

## Troubleshooting

### Compilation Errors

**"Undefined variable"**
→ Make sure variable is declared before use

**"Duplicate declaration"**  
→ Variable already declared with this name

**"Procedure not found"**
→ Check procedure name spelling (case-insensitive internally)

**"Circular dependency"**
→ Modules include each other - reorganize code

### Runtime Issues

**"Zero-page exhausted"**
→ Too many variables/pointers - reduce or use high memory

**"Unexpected END"**
→ Loop/block closing tag mismatch - check for loop keywords

**"Type mismatch"**
→ Assigning wrong type - use appropriate variable type

### Performance Issues

**"Code too large"**
→ Break into multiple procedures or use lookup tables

**"Program too slow"**
→ Use optimization options: `python compiler.py --peepholes`

---

## Best Practices

✅ **DO:**
- Start with the Getting Started guide
- Use meaningful variable names
- Break code into procedures
- Test incrementally
- Profile before optimizing
- Use modules for organization
- Add comments for complex logic
- Check generated assembly

❌ **DON'T:**
- Assume case sensitivity for identifiers
- Create circular module dependencies
- Overuse fixed-address variables
- Ignore zero-page limitations
- Assume local variables are initialized
- Mix memory-mapped I/O carelessly

---

## Additional Resources

### Official
- [GitHub Repository](https://github.com/Dushino/ZAP-compiler)
- [Issue Tracker](https://github.com/Dushino/ZAP-compiler/issues)

### Reference
- [Atari 8-Bit Architecture](https://www.atariarchives.org/)
- [6502 Instruction Set](https://www.masswerk.at/6502/)
- [CC65 Toolchain](https://cc65.github.io/)

### Examples
- `tests/pass/` - Working ZAP programs
- `tests/fail/` - Error test cases
- `p1/` - Sample projects

---

## Document Versions

| Document | Last Updated | Version | Status |
|----------|--------------|---------|--------|
| GETTING_STARTED.md | Jan 2026 | 1.0 | ✅ Complete |
| ZAP_LANGUAGE_REFERENCE.md | Jan 2026 | 1.0 | ✅ Complete |
| ADVANCED_TOPICS.md | Jan 2026 | 1.0 | ✅ Complete |
| grammar.ebnf | Jan 2026 | 2.0 | ✅ Updated |
| project_state.md | Jan 2026 | Updated | ✅ Current |
| advanced_notes.md | Jan 2026 | Reference | ✅ Available |

---

## Contributing to Documentation

Found an issue or want to improve docs?

1. Check existing documentation
2. Open an issue with specifics
3. Submit corrections or additions
4. Follow documentation style guidelines

---

## Contact & Support

- **Repository**: https://github.com/Dushino/ZAP-compiler
- **Issues**: Report bugs or ask questions
- **Discussions**: Share ideas and experiences

---

**Welcome to ZAP! Programming!**

*Whether you're just starting out or an experienced low-level programmer, we hope these documents help you create amazing software for 8-bit systems.*

**Happy coding! 🚀**

---

**Last Updated**: January 19, 2026  
**Documentation Version**: 1.0  
**ZAP! Language Version**: 1.0
