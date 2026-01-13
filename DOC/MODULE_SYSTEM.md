# Action Module System

The Zap compiler supports multi-file compilation using `.module` and `.include` directives.

## Directives

### .module "filename.act"

Marks a file as a module. This is optional but serves as documentation that the file is intended to be included by others.

```action
.module "math_utils.act"

; This module provides math utilities

BYTE result

PROC Add(BYTE a, BYTE b)
    result = a + b
END

FUNC BYTE Square(BYTE x)
RETURN x * x
```

### .include "filename.act"

Includes another module's declarations, procedures, and functions. The included file's symbols become available in the current file.

```action
.include "math_utils.act"

PROC Main()
    BYTE x, y
    
    x = 5
    Add(x, 3)    ; Call procedure from included module
    y = result    ; Access variable from included module
    
    y = Square(4) ; Call function from included module
END
```

## Features

### Automatic Dependency Resolution

The module system automatically loads included files recursively. If `main.act` includes `module_a.act`, and `module_a.act` includes `module_b.act`, all three files are loaded and compiled together.

### Include Guards

Each file is only included once, even if multiple files include it. This prevents duplicate symbol definitions.

```action
; file_a.act includes common.act
; file_b.act includes common.act
; main.act includes both file_a.act and file_b.act
; Result: common.act is only processed once
```

### Circular Dependency Detection

The module system detects circular includes and reports an error:

```
Error: Circular dependency detected: a.act -> b.act -> c.act -> a.act
```

### Symbol Visibility

All top-level declarations from included modules are available:
- Global variables
- Procedures (PROC)
- Functions (FUNC)

Local variables and parameters remain private to their respective procedures/functions.

## Usage

To compile a program with modules:

```bash
python3 compiler.py main.act > output.s
```

The compiler automatically:
1. Loads `main.act`
2. Finds and loads all `.include` directives
3. Recursively loads dependencies
4. Merges all symbols
5. Compiles the complete program

## Preprocessor Directives

The module system integrates with the preprocessor to support conditional compilation.

### .define SYMBOL

Defines a preprocessor symbol that can be tested with `.ifdef` or `.ifndef`.

```zap
.define DEBUG
.define ATARI_PLATFORM
```

### .undef SYMBOL

Undefines a previously defined symbol.

```zap
.undef DEBUG
```

### .ifdef SYMBOL

Conditionally includes code if the symbol is defined (either via `.define` or the `-D` command line option).

```zap
.ifdef DEBUG
  ; This code is only included if DEBUG is defined
  BYTE debug_counter
.endif
```

### .ifndef SYMBOL

Conditionally includes code if the symbol is NOT defined.

```zap
.ifndef RELEASE
  ; This code is included unless RELEASE is defined
  PROC DebugPrint()
    ; Debug implementation
  END
.endif
```

### .else

Provides an alternative branch for `.ifdef` or `.ifndef`.

```zap
.ifdef ATARI_PLATFORM
  ; Atari-specific code
  .include "atari_hardware.zap"
.else
  ; Generic or other platform code
  .include "generic_hardware.zap"
.endif
```

### .endif

Closes an `.ifdef` or `.ifndef` block.

### Command Line Symbol Definition

Symbols can be defined on the command line using the `-D` option:

```bash
python compiler.py program.zap -D DEBUG -D PLATFORM_ATARI -o program.s
```

This is equivalent to having `.define DEBUG` and `.define PLATFORM_ATARI` at the start of the source file, but allows you to control compilation variants without modifying source code.

### Practical Examples

**Platform-specific compilation:**
```zap
.ifdef ATARI
  .segment "DATA"
  screen BYTE = $58
.endif

.ifdef SBC
  .segment "DATA"  
  screen BYTE = $2000
.endif
```

**Debug vs Release builds:**
```zap
PROC Main()
  .ifdef DEBUG
    BYTE error_log[100]
    PROC LogError(BYTE code)
      ; Debug logging code
    END
  .endif
  
  ; Main program code
  .ifdef DEBUG
    LogError(0)
  .endif
END
```

**Feature toggles:**
```zap
.ifdef ENABLE_SOUND
  PROC PlaySound()
    ; Sound implementation
  END
.else
  PROC PlaySound()
    ; Empty stub
  END
.endif
```

## Example

See [tests/test_module_main.act](tests/test_module_main.act) and [tests/math_module.act](tests/math_module.act) for a complete example.

## Implementation

The module system is implemented in [module_system.py](module_system.py):
- `ModuleSystem.load_module()` - Loads a module and its dependencies
- `ModuleSystem.build_program()` - Builds complete program AST from main file
- `ModuleInfo` - Stores parsed module information

The preprocessor is implemented in [preprocessor.py](preprocessor.py):
- `Preprocessor.process()` - Processes conditional compilation directives
- Symbols defined via `-D` are shared across all modules in a compilation
