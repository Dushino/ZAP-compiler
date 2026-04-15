---
---

# ZAP!

A high-level language that compiles to **6502 / 65C02 assembly**, targeting **Atari 8-bit** computers. Combines high-level constructs (structs, enums, functions, loops) with low-level control (pointers, hardware registers, inline assembly) and produces tight, optimized 6502 code.

[Get started](GETTING_STARTED) · [View on GitHub](https://github.com/Dushino/ZAP-compiler)

---

## Quickstart

Save this as `hello.zap`:

```zap
.include "lib/atari/atari_stdio.zap"

proc main()
    puts("Hello, ZAP!")
end
```

Compile, assemble, and link:

```bash
zapc --cpu 6502 -O1 -I lib hello.zap -o hello.s
ca65 hello.s -o hello.o
ld65 -C cfg/my_atari.cfg hello.o -o hello.xex
```

The resulting `hello.xex` runs on any Atari 8-bit emulator (Altirra, Atari800) or real hardware.

## Performance

In benchmark comparisons, ZAP! generates code that runs **~44% faster than Action!** on the Atari 8-bit platform.

## Documentation

Browse the guides using the sidebar, or start with:

- [Getting Started Guide](GETTING_STARTED) — beginner tutorial
- [Language Reference](ZAP_LANGUAGE_REFERENCE) — complete language spec
- [Advanced Topics](ADVANCED_TOPICS) — pointers, inline assembly, optimization
- [Standard Library](STDLIB) — built-in functions and modules
- [Error Messages](ERROR_MESSAGES) — compiler error catalog
- [Known Limitations](KNOWN_LIMITATIONS) — current limitations
- [Architecture](ARCHITECTURE) — how the compiler works internally
- [IDE Integration](IDE_INTEGRATION) — VS Code setup

## License

ZAP! is released under the [GNU General Public License v3.0](https://github.com/Dushino/ZAP-compiler/blob/main/LICENSE).
