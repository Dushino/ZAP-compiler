# ZAP! Standard Library — Quick Reference

Full API documentation: [docs/STDLIB.md](../docs/STDLIB.md) · [online version](https://dushino.github.io/ZAP-compiler/STDLIB.html)

---

## Module Index

| Module name     | File                         | Platform       | Description |
|-----------------|------------------------------|----------------|-------------|
| `"errno"`       | `lib/errno.zap`              | All            | Error code enum (`ERRNO`) using Atari CIO status bytes |
| `"types"`       | `lib/types.zap`              | All            | Core types: `BOOL`, `FILE`, `SEEK`, `NULL` |
| `"string"`      | `lib/string.zap`             | All            | Memory & string functions (C `string.h`-style) |
| `"stdio"`       | `lib/stdio.zap`              | Multi-platform | I/O coordinator; selects platform at compile time; shared print helpers |
| `"atari_stdio"` | `lib/atari/atari_stdio.zap`  | Atari 8-bit    | Screen, keyboard, and file I/O via Atari CIO |
| _(none)_        | `lib/atari/atari_gtia.zap`   | Atari 8-bit    | GTIA chip registers — colors, sprites, collision |
| _(none)_        | `lib/atari/atari_pokey.zap`  | Atari 8-bit    | POKEY chip registers — sound, keyboard, paddles, serial |
| _(none)_        | `lib/atari/PIA.zap`          | Atari 8-bit    | PIA chip registers — parallel I/O ports |

### Non-module support files

| File                             | Purpose |
|----------------------------------|---------|
| `lib/atari/atari.inc`            | Atari system equates (ca65 include) |
| `lib/atari/atari_antic.inc`      | ANTIC display-list chip equates (ca65 include) |
| `lib/atari/exehdr.s`             | Atari executable header (ca65 assembly, auto-linked) |
| `lib/sbc/vectors.s`              | 6502 SBC reset/NMI/IRQ vector table (experimental) |

Files without a `.module` declaration are plain include files with no module name and no dependencies. They expose `#PORT` hardware-register declarations that any `.zap` source can `.include` directly.

---

## Dependency Graph

```
errno  ←  types  ←  string
                ↖
                 stdio  ←  [-D ATARI]  atari_stdio
```

- Everything depends transitively on `errno` and `types`.
- `stdio` is a platform coordinator — it conditionally includes `atari_stdio.zap` when `-D ATARI` is set, and would include an SBC implementation if one existed.
- `stdio` also owns the shared **BCD print helpers** (`printb`, `printw`, `printl`, `putx`, `putxw`) that use 6502 SED mode double-dabble conversion and work on any platform.

---

## How to Include

Point the compiler at `lib/` with `-I`, then include modules by relative path:

```zap
.include "string.zap"
.include "stdio.zap"
```

Hardware register files can be included directly:

```zap
.include "atari/atari_gtia.zap"
.include "atari/atari_pokey.zap"
```

**Compiling for Atari** (activates `atari_stdio` inside `stdio`):

```bash
zapc program.zap -D ATARI -6502 -I lib -o program.s
```

---

## Quick API Summary

Full signatures, semantics, and examples live in [docs/STDLIB.md](../docs/STDLIB.md). The tables below are a cheat sheet.

### string.zap — Memory & Strings

| Symbol     | Kind | Signature |
|------------|------|-----------|
| `memchr`   | func | `byte^ memchr(byte^ ptr, const byte val, const word len)` |
| `memcmp`   | func | `byte memcmp(byte^ ptr1, byte^ ptr2, const word len)` |
| `memcpy`   | proc | `memcpy(byte^ dst, byte^ src, const word len)` |
| `memset`   | proc | `memset(byte^ dst, const byte val, const word len)` |
| `strlen`   | func | `byte strlen(byte^ ptr, const byte max=255)` |
| `strncat`  | proc | `strncat(byte^ dst, byte^ src, byte max=255)` |
| `strnchr`  | func | `byte^ strnchr(byte^ ptr, const byte val, const byte max)` |
| `strncmp`  | func | `byte strncmp(byte^ str1, byte^ str2, const byte max)` |
| `strncpy`  | proc | `strncpy(byte^ dst, byte^ src, const byte max)` |

### stdio.zap — Shared Print Helpers (all platforms)

| Symbol    | Kind | Description |
|-----------|------|-------------|
| `putx`    | proc | Print byte as 2 hex digits |
| `putxw`   | proc | Print word as 4 hex digits |
| `printb`  | proc | Print byte as decimal, with leading-zero & right-align options |
| `printw`  | proc | Print word as decimal, same options |
| `printl`  | proc | Print long (32-bit) as decimal, same options |

All decimal print functions share a single BCD conversion engine (`print_convert` + `print_decimal`, both `#noexport`) based on 6502 SED mode double-dabble.

### atari_stdio.zap — Screen Output

| Symbol            | Kind | Description |
|-------------------|------|-------------|
| `cls`             | proc | Clear screen and reset cursor |
| `graphics`        | proc | Set screen graphics mode (via CIO `S:` device) |
| `putchar`         | proc | Print one character (handles `\n`, `\t`, `\0`) |
| `puts`            | proc | Print null-terminated string |
| `crlf`            | proc | Move to next line, scroll if needed |
| `gotoxy`          | proc | Move cursor to `(x, y)` |
| `cursor_on`       | proc | Show cursor (inverse video) |
| `cursor_off`      | proc | Hide cursor |
| `ascii_to_screen` | func | Convert ATASCII code to internal screen code |
| `SCREEN_X_SIZE`   | const | `40` |
| `SCREEN_Y_SIZE`   | const | `24` |

### atari_stdio.zap — Keyboard Input

| Symbol       | Kind | Description |
|--------------|------|-------------|
| `getchar`    | func | Wait for key, return ATASCII code |
| `getc`       | func | Alias for `getchar` |
| `getcblink`  | func | Wait for key with blinking cursor |
| `gets`       | func | Read line with editing (backspace, arrows) |
| `delay`      | proc | Wait N vertical blanks (~1/60 s each) |

### atari_stdio.zap — File I/O

| Symbol     | Kind  | Status | Description |
|------------|-------|--------|-------------|
| `fopen`    | func  | ✅ OK  | Open device/file |
| `fclose`   | func  | ✅ OK  | Close file |
| `fread`    | func  | ✅ OK  | Read buffer from file |
| `fwrite`   | func  | ✅ OK  | Write buffer to file |
| `fgetc`    | func  | ✅ OK  | Read single character |
| `fputc`    | func  | ✅ OK  | Write single character |
| `fputs`    | func  | ✅ OK  | Write string to file |
| `feof`     | func  | ✅ OK  | Check EOF flag |
| `ferror`   | func  | ✅ OK  | Get last error |
| `rename`   | func  | ✅ OK  | Rename file |
| `remove`   | func  | ✅ OK  | Delete file |
| `CIO`      | func  | ✅ OK  | Low-level CIO dispatch — usually called indirectly |
| `rewind`   | func  | ⚠️  stub  | Calls `fseek` — not implemented |
| `fseek`    | func  | ❌ TODO | Seek in file |
| `ftell`    | func  | ❌ TODO | Get file position |
| `fprintf`  | func  | ❌ TODO | Formatted print to file |
| `fscanf`   | func  | ❌ TODO | Formatted read from file |

### errno.zap — Status & Error Codes

| Symbol | Kind  | Description |
|--------|-------|-------------|
| `ERRNO`| enum  | Atari CIO status bytes. `OK = 0` (API-level success), `SUCCESS = 1` (raw CIO success), errors in `$80–$FF`. |

### types.zap — Core Types

| Symbol             | Kind          | Description |
|--------------------|---------------|-------------|
| `BOOL`             | enum          | `FALSE = 0`, `TRUE = 1` |
| `FILE`             | struct        | Open-file handle (fd, error, eof flags) |
| `SEEK`             | enum          | `SET`, `CUR`, `END` (placeholders for future `fseek`) |
| `NULL`             | const word    | Null pointer (`$0000`) |
| `FILE_HANDLE_MAX`  | const byte    | Maximum simultaneous open handles (`4`) |

---

## Hardware Register Files (Atari)

These files expose chip registers as `#PORT` declarations you can read and write directly like variables. They declare no functions or procedures, they have no `.module` name, and they don't depend on anything — just `.include` them where you need hardware access.

- **`atari_gtia.zap`** — GTIA: colors (`COLBK`, `COLPF0..3`), player/missile position and shape, collision registers, triggers
- **`atari_pokey.zap`** — POKEY: audio channels (`AUDF1..4`, `AUDC1..4`, `AUDCTL`), keyboard matrix, paddles, random number generator, serial I/O
- **`PIA.zap`** — PIA 6520: joystick ports, control registers

See [docs/STDLIB.md](../docs/STDLIB.md) for per-register descriptions and usage examples.
