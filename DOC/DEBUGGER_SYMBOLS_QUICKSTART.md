# Quick Start: Debugger Symbols in ZAP Compiler

## TL;DR

Your ZAP compiler now automatically generates debug symbols. Just build normally and use the generated `.lbl` file in your debugger.

## Build & Debug

### Compile with Debug Symbols
```bash
# Linux/macOS
make atari

# Windows
make.bat atari
```

This generates:
- `out/p1.com` - Your executable
- `out/p1.lbl` - Debug symbols (VICE format)

### Debug with VICE

**Option 1: Start with symbols**
```bash
x64sc -moncommands out/p1.lbl out/p1.prg
```

**Option 2: Load in monitor**
```
ll "out/p1.lbl"
```

### Debug in VICE Monitor

```
# Disassemble from procedure
d ._main

# Set breakpoint
break ._main

# Print variable value
print _my_var

# Jump to address
jump ._my_procedure
```

### Debug with Oricutron

```
# Load symbols
sl out/p1.sym

# Use same commands as VICE
d ._main
break ._main
```

## What's Available

All your ZAP code symbols:
- `_main` - Main procedure
- `_proc_name` - Any procedure you define
- `_func_name` - Any function you define
- `_var_name` - Global variables
- `_array_name` - Arrays
- Local variables inside procedures/functions

## Symbol Naming

| ZAP Code | Symbol Name |
|----------|------------|
| `proc hello()` | `_hello` |
| `func byte getX()` | `_getX` |
| `var count: word` | `_count` |
| `byte buffer[256]` | `_buffer` |

## No Configuration Needed

Debug symbol generation is:
- ✅ Automatic (no flags or options needed)
- ✅ Transparent (works with existing build system)
- ✅ Free (no runtime or binary size cost)
- ✅ Built-in (integrated into compiler)

## How It Works

1. Compiler emits `.DEBUGINFO +` in generated assembly
2. Assembler (`ca65 -g`) embeds symbols in object file
3. Linker (`ld65 -Ln`) generates `.lbl` symbol file
4. Debugger loads `.lbl` file and enables symbol-based debugging

## Example Workflow

```
1. Write your ZAP program
   └─ my_program.zap

2. Build it
   └─ make atari
   └─ Generates: out/p1.com + out/p1.lbl

3. Start VICE
   └─ x64sc -moncommands out/p1.lbl

4. Debug with symbols
   └─ break ._main
   └─ d ._my_function
   └─ print _my_variable
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| No `.lbl` file | Check build output for errors |
| Symbols not recognized in VICE | Remember dot prefix: `._main` not `_main` |
| Can't set breakpoint | Ensure label file is loaded with `ll` command |

## More Info

- 📖 [Full Documentation](DEBUGGER_SYMBOLS.md)
- 🔧 [Implementation Details](DEBUGGER_SYMBOLS_IMPLEMENTATION.md)
- 📚 [cc65 Debugging Guide](https://cc65.github.io/doc/debugging.html)

---

**Status**: ✅ Fully implemented and ready to use!
