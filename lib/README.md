# ZAP! Standard Library — Quick Reference

Full API documentation: [docs/STDLIB.md](../docs/STDLIB.md)

---

## Module Index

| Module name | File | Platform | Description |
|-------------|------|----------|-------------|
| `"errno"` | `lib/errno.zap` | All | Error code enum (`ERRNO`) |
| `"types"` | `lib/types.zap` | All | Core types: `BOOL`, `FILE`, `SEEK`, `NULL` |
| `"string"` | `lib/string.zap` | All | Memory & string functions (C `string.h`-style) |
| `"stdio"` | `lib/stdio.zap` | Multi-platform | I/O coordinator; selects platform impl at compile time |
| `"atari_stdio"` | `lib/atari/atari_stdio.zap` | Atari 8-bit | Screen/keyboard/file I/O via Atari CIO |
| _(none)_ | `lib/atari/atari_gtia.zap` | Atari 8-bit | GTIA chip registers — sprites, color, collision |
| _(none)_ | `lib/atari/atari_pokey.zap` | Atari 8-bit | POKEY chip registers — sound, keyboard, paddles |
| _(none)_ | `lib/atari/PIA.zap` | Atari 8-bit | PIA chip registers — parallel I/O ports |

---

## Dependency Graph

```
errno  ←  types  ←  string
                        ↑
errno  ←  types  ←  stdio  ←  [ATARI]  atari_stdio
```

Files without a `.module` declaration (`atari_gtia.zap`, `atari_pokey.zap`, `PIA.zap`) are plain include files with no module name and no dependencies.

---

## How to Include

Use the `-I` flag to set the include path to the `lib/` directory, then include modules by relative path:

```zap
.include "string.zap"
.include "stdio.zap"
```

Or include hardware definition files directly:

```zap
.include "atari/atari_gtia.zap"
.include "atari/atari_pokey.zap"
```

**Compile for Atari** (activates atari_stdio):

```
zapc program.zap -D ATARI -6502 -I work/lib -o program.s
```

---

## Quick API Summary

### string.zap — Memory & Strings

| Symbol | Kind | Signature |
|--------|------|-----------|
| `memchr` | func | `byte^ memchr(byte^ ptr, const byte val, const word len)` |
| `memcmp` | func | `byte memcmp(byte^ ptr1, byte^ ptr2, const word len)` |
| `memcpy` | proc | `memcpy(byte^ dst, byte^ src, const word len)` |
| `memmove` | proc | `memmove(byte^ dst, byte^ src, const word len)` |
| `memset` | proc | `memset(byte^ dst, const byte val, const word len)` |
| `strlen` | func | `byte strlen(byte^ ptr, const byte max=255)` |
| `strncmp` | func | `byte strncmp(byte^ str1, byte^ str2, const byte max)` |
| `strnchr` | func | `byte^ strnchr(byte^ ptr, const byte val, const byte max)` |
| `strncat` | proc | `strncat(byte^ dst, byte^ src, const byte max)` |
| `strncpy` | proc | `strncpy(byte^ dst, byte^ src, const byte max)` |

### atari_stdio.zap — Screen Output

| Symbol | Kind | Description |
|--------|------|-------------|
| `cls` | proc | Clear screen, reset cursor |
| `putchar` | proc | Print one character (handles `\n`, `\t`, `\0`) |
| `puts` | proc | Print null-terminated string |
| `crlf` | proc | Move to next line, scroll if needed |
| `gotoxy` | proc | Move cursor to `(x, y)` |
| `cursor_on` | proc | Show cursor (inverse video) |
| `cursor_off` | proc | Hide cursor |
| `putx` | proc | Print byte as 2 hex digits |
| `printb` | proc | Print byte as decimal (with options) |

### atari_stdio.zap — Keyboard Input

| Symbol | Kind | Description |
|--------|------|-------------|
| `getchar` | func | Wait for key, return ATASCII code |
| `getc` | func | Alias for `getchar` |
| `getcblink` | func | Wait for key with blinking cursor |
| `gets` | func | Read line with editing (backspace, arrows) |
| `delay` | proc | Wait N vertical blanks (~1/60 s each) |

### atari_stdio.zap — File I/O

| Symbol | Kind | Status | Description |
|--------|------|--------|-------------|
| `fopen` | func | OK | Open device/file |
| `fclose` | func | OK | Close file |
| `fwrite` | func | OK | Write buffer to file |
| `feof` | func | OK | Check EOF flag |
| `ferror` | func | OK | Get last error |
| `rewind` | func | stub | Rewind (calls fseek — not implemented) |
| `fread` | func | TODO | Read buffer from file |
| `fseek` | func | TODO | Seek in file |
| `ftell` | func | TODO | Get file position |
| `fgetc` | func | TODO | Read single character |
| `fputc` | func | TODO | Write single character |
| `rename` | func | TODO | Rename file |
| `remove` | func | TODO | Delete file |
| `fprintf` | func | TODO | Formatted print to file |
| `fputs` | func | TODO | Write string to file |
| `fscanf` | func | TODO | Formatted read from file |
