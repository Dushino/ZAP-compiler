# ZAP! Standard Library Reference

This document describes all modules and hardware-definition files shipped with the ZAP! compiler in the `work/lib/` directory.

---

## Table of Contents

1. [Overview](#overview)
2. [Module Dependency Tree](#module-dependency-tree)
3. [Module: errno](#module-errno--error-codes)
4. [Module: types](#module-types--core-types)
5. [Module: string](#module-string--memory--string-functions)
6. [Module: stdio](#module-stdio--io-coordinator)
7. [Module: atari_stdio](#module-atari_stdio--atari-8-bit-io)
8. [Hardware Definition Files](#hardware-definition-files)
   - [atari_gtia.zap — GTIA Chip](#atari_gtiazap--gtia-chip)
   - [atari_pokey.zap — POKEY Chip](#atari_pokeyzap--pokey-chip)
   - [PIA.zap — PIA Chip](#piazap--pia-chip)
9. [Implementation Status Matrix](#implementation-status-matrix)
10. [Usage Examples](#usage-examples)

---

## Overview

The ZAP! standard library provides reusable building blocks for programs targeting Atari 8-bit computers and other 6502-based systems. Libraries are organised as **modules** (files containing a `.module` declaration) and **hardware definition files** (plain include files with no module declaration).

To use a module in your program:

```zap
.include "lib/string.zap"
.include "lib/stdio.zap"
```

For Atari-specific I/O, define `ATARI` at compile time:

```
zapc program.zap -D ATARI -6502 -o program.s
```

---

## Module Dependency Tree

```
errno
└── (no dependencies)

types
└── errno

string
├── errno
└── types

stdio  (platform coordinator)
├── errno
├── types
└── [ATARI]  atari_stdio
              ├── errno
              ├── types
              └── string

atari_gtia   (hardware defs, no module)
atari_pokey  (hardware defs, no module)
PIA          (hardware defs, no module)
```

---

## Module: errno — Error Codes

**File:** `work/lib/errno.zap`
**Module name:** `"errno"`
**Platform:** All
**Depends:** nothing

Defines the `ERRNO` enum with Linux kernel-compatible error codes plus Atari CIO status codes (documented in a comment block at the end of the file).

### Enum `ERRNO`

| Value | Code | Meaning |
|-------|------|---------|
| 0 | `OK` | No error |
| 1 | `E2BIG` | Argument list too long |
| 2 | `EACCES` | Permission denied |
| 3 | `EAGAIN` | Resource temporarily unavailable |
| 4 | `EALREADY` | Connection already in progress |
| 5 | `EBADF` | Bad file descriptor |
| 6 | `EBADFD` | File descriptor in bad state |
| 7 | `EBADRQC` | Invalid request code |
| 8 | `EBUSY` | Device or resource busy |
| 9 | `ECANCELED` | Operation canceled |
| 10 | `ECHRNG` | Channel number out of range |
| 11 | `ECOMM` | Communication error on send |
| 12 | `ECONNABORTED` | Connection aborted |
| 13 | `ECONNREFUSED` | Connection refused |
| 14 | `ECONNRESET` | Connection reset |
| 15 | `EEXIST` | File exists |
| 16 | `EFBIG` | File too large |
| 17 | `EHOSTUNREACH` | Host is unreachable |
| 18 | `EHWPOISON` | Hardware error |
| 19 | `EILSEQ` | Invalid sequence |
| 20 | `EINPROGRESS` | Operation in progress |
| 21 | `EINTR` | Interrupted |
| 22 | `EINVAL` | Invalid argument |
| 23 | `EIO` | I/O error |
| 24 | `EISCONN` | Connection already in progress |
| 25 | `EISDIR` | Is a directory |
| 26 | `EMFILE` | Too many files |
| 27 | `EMSGSIZE` | Message too long |
| 28 | `ENAMETOOLONG` | Filename too long |
| 29 | `ENETDOWN` | Network down |
| 30 | `ENETRESET` | Network reset |
| 31 | `ENETUNREACH` | Network unreachable |
| 32 | `ENOANO` | No anonymous node |
| 33 | `ENODATA` | No data |
| 34 | `ENODEV` | No device |
| 35 | `ENOENT` | No entry |
| 36 | `ENOEXEC` | No execute |
| 37 | `ENOLINK` | No link |
| 38 | `ENOMEDIUM` | No medium |
| 39 | `ENOMEM` | No memory |
| 40 | `ENOMSG` | No message |
| 41 | `ENONET` | No network |
| 42 | `ENOPROTOOPT` | No protocol option |
| 43 | `ENOSPC` | No space |
| 44 | `ENOSR` | No stream resources |
| 45 | `ENOSTR` | No stream |
| 46 | `ENOSYS` | No system call |
| 47 | `ENOTBLK` | Not a block device |
| 48 | `ENOTCONN` | Not connected |
| 49 | `ENOTDIR` | Not a directory |
| 50 | `ENOTEMPTY` | Directory not empty |
| 51 | `ENOTRECOVERABLE` | Not recoverable |
| 52 | `ENOTSOCK` | Not a socket |
| 53 | `ENOTSUP` | Not supported |
| 54 | `ENOTUNIQ` | Not unique |
| 55 | `ENXIO` | No such device or address |
| 56 | `EOPNOTSUPP` | Operation not supported |
| 57 | `EPROTO` | Protocol error |
| 58 | `EPROTONOSUPPORT` | Protocol not supported |
| 59 | `ERANGE` | Value too large |
| 60 | `EREMCHG` | Remote address changed |
| 61 | `EREMOTEIO` | Remote I/O error |
| 62 | `EROFS` | Read-only file system |
| 63 | `ESHUTDOWN` | Cannot send after socket shutdown |
| 64 | `ESPIPE` | Invalid seek |
| 65 | `ESOCKTNOSUPPORT` | Socket type not supported |
| 66 | `ESRCH` | No such process |
| 67 | `ESTALE` | File handle is stale |
| 68 | `ESTRPIPE` | Stream pipe error |
| 69 | `ETIME` | Timer expired |
| 70 | `ETIMEDOUT` | Connection timed out |
| 71 | `ETXTBSY` | Text file busy |
| 72 | `EUCLEAN` | File system needs cleaning |
| 73 | `EUNATCH` | Protocol driver not attached |
| 74 | `EWOULDBLOCK` | Operation would block |
| 75 | `EXDEV` | Cross-device link |
| 76 | `EXFULL` | Exchange full |

### Atari CIO Status Codes

The source file contains a reference comment listing Atari CIO status byte values (0x01–0xAB). These are the raw numbers returned by the CIO handler; they do **not** map directly to `ERRNO` enum values. See the comment block in `errno.zap` for the full table.

---

## Module: types — Core Types

**File:** `work/lib/types.zap`
**Module name:** `"types"`
**Platform:** All
**Depends:** `errno`

Provides fundamental type definitions and file-I/O structures used throughout the standard library.

### Enum `BOOL`

```zap
enum BOOL
    FALSE,   ; 0
    TRUE     ; 1
end
```

### Struct `FILE`

Represents an open file handle. Pass `FILE^` pointers to all file I/O functions.

```zap
struct FILE
    byte  fd      ; CIO IOCB channel number (filled by fopen)
    ERRNO error   ; last error code (ERRNO.OK = no error)
    BOOL  eof     ; BOOL.TRUE when end-of-file has been reached
end
```

### Constants

| Name | Type | Value | Meaning |
|------|------|-------|---------|
| `NULL` | `word` | `$0000` | Null pointer |
| `FILE_HANDLE_MAX` | `byte` | `4` | Maximum simultaneously open file handles |

### Enum `SEEK`

Seek-position anchors for `fseek()`.

| Value | Code | Meaning |
|-------|------|---------|
| 0 | `SEEK_SET` | Seek from start of file |
| 1 | `SEEK_CUR` | Seek from current position |
| 2 | `SEEK_END` | Seek from end of file |

---

## Module: string — Memory & String Functions

**File:** `work/lib/string.zap`
**Module name:** `"string"`
**Platform:** All
**Depends:** `errno`, `types`

C `string.h`-inspired memory and string manipulation routines. All strings are null-terminated byte arrays. Functions that scan memory accept an explicit length or `max` limit.

### Functions

#### `func byte^ memchr(byte^ ptr, const byte val, const word len)`

Scans `len` bytes starting at `ptr` for the first occurrence of `val`.

- **Returns:** pointer to the matching byte, or `NULL` if not found.

```zap
byte^ found = memchr(buffer, '$', 256)
if found != NULL
    ; ...
end
```

---

#### `func byte memcmp(byte^ ptr1, byte^ ptr2, const word len)`

Compares `len` bytes of two memory blocks numerically.

- **Returns:** `0` = equal, `1` = first block is larger, `2` = second block is larger.

---

#### `func byte strlen(byte^ ptr, const byte max=255)`

Returns the length of a null-terminated string, up to `max` characters.

- **Returns:** number of characters before the null terminator (0–max).
- Default `max` is 255.

```zap
byte len = strlen(mystr)
```

---

#### `func byte strncmp(byte^ str1, byte^ str2, const byte max)`

Compares up to `max` characters of two strings.

- **Returns:** `0` = equal, `1` = first string is larger, `2` = second string is larger.

---

#### `func byte^ strnchr(byte^ ptr, const byte val, const byte max)`

Searches up to `max` characters of string `ptr` for `val`. Stops at null terminator.

- **Returns:** pointer to the first matching character, or `NULL`.

---

### Procedures

#### `proc memcpy(byte^ dst, byte^ src, const word len)`

Copies `len` bytes from `src` to `dst`. Regions must not overlap (use `memmove` for overlapping regions).

---

#### `proc memmove(byte^ dst, byte^ src, const word len)`

Copies `len` bytes from `src` to `dst`, correctly handling overlapping regions by copying backwards when `dst > src`.

---

#### `proc memset(byte^ dst, const byte val, const word len)`

Fills `len` bytes starting at `dst` with `val`.

```zap
memset(screen_buf, 0, 1000)   ; clear 1000 bytes
```

---

#### `proc strncat(byte^ dst, byte^ src, const byte max)`

Appends up to `max` bytes from `src` to the end of null-terminated string `dst`. Locates the end of `dst` with `strlen` first.

---

#### `proc strncpy(byte^ dst, byte^ src, const byte max)`

Copies up to `max` characters from `src` to `dst`. Stops at (and includes) the null terminator.

---

## Module: stdio — I/O Coordinator

**File:** `work/lib/stdio.zap`
**Module name:** `"stdio"`
**Platform:** Multi-platform (conditional)
**Depends:** `errno`, `types`

Acts as a thin coordinator that selects the platform-specific I/O implementation at compile time via preprocessor directives.

```
-D ATARI  →  includes lib/atari/atari_stdio.zap
-D SBC    →  includes lib/sbc/sbc_stdio.zap  (not yet implemented)
```

### Exported symbols

| Symbol | Kind | Description |
|--------|------|-------------|
| `CONSTRUCTOR` | proc | Module init stub (empty; actual init is in platform file) |

All I/O functions (putchar, puts, getchar, fopen, …) are provided by the included platform file and become part of the `stdio` module's exported namespace.

### Usage

```zap
.include "lib/stdio.zap"

proc main()
    puts("Hello, Atari!\n")
end
```

Compile for Atari:

```
zapc program.zap -D ATARI -6502 -o program.s
```

---

## Module: atari_stdio — Atari 8-bit I/O

**File:** `work/lib/atari/atari_stdio.zap`
**Module name:** `"atari_stdio"`
**Platform:** Atari 400/800/XL/XE (6502/65C02)
**Depends:** `errno`, `types`, `string`

Complete Atari 8-bit I/O library. Provides direct-mapped text-mode screen output, keyboard input with cursor support, and file I/O via the Atari CIO (Computer Input/Output) subsystem. Critical sections use inline 6502 assembly for performance.

> **Note:** `atari_stdio` is normally included indirectly through `stdio` when `-D ATARI` is defined. It can also be included directly if needed.

### Screen Constants

| Name | Type | Value | Meaning |
|------|------|-------|---------|
| `SCREEN_X_SIZE` | `const byte` | `40` | Screen width in characters |
| `SCREEN_Y_SIZE` | `const byte` | `24` | Screen height in characters |

### Keyboard Key Code Constants

| Constant | ATASCII Value | Key |
|----------|--------------|-----|
| `ATARI_KEY_RETURN` | `$9B` | Return / Enter |
| `ATARI_KEY_LEFT` | `$1E` | Left arrow |
| `ATARI_KEY_RIGHT` | `$1F` | Right arrow |
| `ATARI_KEY_UP` | `$1C` | Up arrow |
| `ATARI_KEY_DOWN` | `$1D` | Down arrow |
| `ATARI_KEY_CTRL_LEFT` | `$2B` | Ctrl+Left |
| `ATARI_KEY_CTRL_RIGHT` | `$2A` | Ctrl+Right |
| `ATARI_KEY_CTRL_UP` | `$2D` | Ctrl+Up |
| `ATARI_KEY_CTRL_DOWN` | `$3D` | Ctrl+Down |
| `ATARI_KEY_HOME` | `$7D` | Clear/Home |
| `ATARI_KEY_DELETE` | `$FE` | Delete |
| `ATARI_KEY_INSERT` | `$FF` | Insert |
| `ATARI_KEY_BACKSPACE` | `$7E` | Backspace |
| `ATARI_KEY_ESCAPE` | `$1B` | Escape |

### Hardware Variables

| Name | Address | Description |
|------|---------|-------------|
| `KBHIT` | `@764` | Keyboard status — 255 = no key pressed |
| `TIMER` | `@20` | Atari vertical blank counter (60 Hz) |
| `kbcode` | `@$D209` | POKEY keyboard scan code |
| `scr1` | `@40000` | Default screen memory base |

### Struct `IOCB_Block`

Maps the Atari Input/Output Control Block layout. Eight IOCB blocks exist at `$0340`–`$03BF`, one per CIO channel.

```zap
struct IOCB_Block
    byte ICHID   ; handler identifier ($FF = free)
    byte ICDNO   ; device number (disk drive number)
    byte ICCOM   ; command code (see ICCOM_COMMANDS)
    byte ICSTA   ; status byte returned by CIO
    word ICBA    ; buffer address
    word ICPT    ; put-byte routine address
    word ICBL    ; buffer length
    byte ICAX1   ; auxiliary byte 1 (access mode for Open)
    byte ICAX2   ; auxiliary byte 2
    byte ICAX3   ; auxiliary byte 3
    byte ICAX4   ; auxiliary byte 4
    byte ICAX5   ; auxiliary byte 5
    byte ICAX6   ; auxiliary byte 6
end

IOCB_Block IOCB[8] @$0340   ; 8 CIO channels
```

### Enum `ICCOM_COMMANDS`

CIO command codes written to `IOCB.ICCOM`:

| Value | Name | Description |
|-------|------|-------------|
| `$03` | `Open` | Open device/file |
| `$0C` | `Close` | Close device/file |
| `$07` | `GetChr` | Read single character |
| `$0B` | `PutChr` | Write single character / buffer |
| `$05` | `GetRec` | Read record (line) |
| `$09` | `PutRec` | Write record (line) |
| `$0D` | `Status` | Get device status |

### Enum `ICAX1_Mode`

File access modes written to `IOCB.ICAX1` when opening a file (DOS 2.0):

| Value | Name | Description |
|-------|------|-------------|
| `4` | `Read` | Input; position to start of file |
| `6` | `Directory` | Read disk directory |
| `8` | `Write` | Output; position to start (overwrites) |
| `9` | `Append` | Output; position to end of file |
| `12` | `ReadWrite` | Input/output; position to start |

---

### Screen Output Functions

#### `proc cls()`

Clears the screen and resets the cursor to position (0, 0).

---

#### `proc putchar(byte ch)`

Outputs one character at the current cursor position and advances the cursor. Handles:
- `'\n'` (newline) — calls `crlf()` to move to next line, scroll if needed
- `'\t'` (tab) — advances to the next 4-character tab stop
- `'\0'` (null) — ignored

Converts ATASCII to screen codes internally via `ascii_to_screen()`.

---

#### `proc puts(byte^ str)`

Prints a null-terminated string to the screen by calling `putchar()` for each character.

```zap
puts("Score: ")
```

---

#### `proc crlf()`

Moves the cursor to column 0 of the next line. If already on the last row, scrolls the screen up one line and clears the bottom row.

---

#### `proc gotoxy(byte x, byte y)`

Moves the cursor to absolute screen coordinates `(x, y)` where `(0, 0)` is the top-left corner.

```zap
gotoxy(10, 5)
puts("Hello")
```

---

#### `proc cursor_on()`

Turns on the cursor by setting the inverse-video bit of the current screen cell.

---

#### `proc cursor_off()`

Turns off the cursor by clearing the inverse-video bit of the current screen cell.

---

#### `proc putx(byte value)`

Prints a byte as two uppercase hexadecimal characters (e.g., `$2A` → `"2A"`).

```zap
puts("Status: $")
putx(IOCB[3].ICSTA)
```

---

#### `proc printb(byte arg, const byte lzero=1, const byte ralign=1)`

Prints a byte (0–255) as a decimal number.

- `lzero=1` — show leading zeros (e.g., `007`); `0` = suppress leading zeros
- `ralign=1` — right-align by padding spaces on the left; `0` = no padding

```zap
printb(score)           ; "042" (default: leading zeros, right-align)
printb(score, 0, 0)     ; "42"  (no leading zeros, no padding)
```

---

#### `func byte ascii_to_screen(byte ch)`

Converts an ATASCII character code to the corresponding Atari screen memory code, handling the inverse-video bit correctly. Used internally by `putchar()`.

---

### Keyboard Input Functions

#### `func byte getchar()`

Waits for a key press using the Atari keyboard handler ($E424/$E425) and returns the ATASCII key code. Does not echo the character.

---

#### `func byte getc()`

Alias for `getchar()`.

---

#### `func byte getcblink()`

Same as `getchar()` but shows a blinking cursor while waiting. The cursor blinks at approximately 1.5 Hz (20 timer ticks on, 20 off).

- **Returns:** ATASCII key code of the pressed key.

---

#### `func byte gets(const byte^ buffer, const byte max_len)`

Reads a line of input from the keyboard into `buffer` (up to `max_len` characters), with full editing support:

- Printable characters are echoed and inserted at the cursor position.
- `BACKSPACE` deletes the character before the cursor.
- `DELETE` deletes the character at the cursor.
- `LEFT` / `RIGHT` move the cursor within the input.
- `RETURN`, `ESCAPE`, `UP`, `DOWN` terminate input immediately.

- **Returns:** the terminating key code (`ATARI_KEY_RETURN`, `ATARI_KEY_ESCAPE`, etc.).

---

#### `proc delay(byte delay)`

Waits for `delay` vertical blank interrupts (roughly `delay / 60` seconds at 60 Hz NTSC).

```zap
delay(60)   ; wait approximately 1 second
```

---

### File I/O Functions

File I/O uses the Atari CIO system. Each open file occupies one IOCB channel (channels 3–7 are available; 0 is the screen editor, 1–2 are reserved).

#### `func byte fopen(FILE^ fd, byte^ filename, byte mode)`

Opens a file or device.

- `fd` — pointer to a caller-allocated `FILE` struct
- `filename` — Atari device/filename, e.g. `"D:FILE.TXT"`, `"P:"` (printer)
- `mode` — one of the `ICAX1_Mode` enum values
- **Returns:** `ERRNO.OK` on success, or a CIO error code on failure.
- Sets `fd^.error` and `fd^.eof` accordingly.

```zap
FILE myfile
if fopen(@myfile, "D:HELLO.TXT", ICAX1_Mode.Write) == ERRNO.OK
    fwrite(@myfile, "Hello!\n", 7)
    fclose(@myfile)
end
```

---

#### `func ERRNO fclose(FILE^ fd)`

Closes an open file and frees its IOCB channel.

- **Returns:** `ERRNO.OK` on success.

---

#### `func word fwrite(FILE^ fd, byte^ buffer, word size)`

Writes `size` bytes from `buffer` to the open file using CIO `PutChr`.

- **Returns:** `ERRNO.OK` on success, or a CIO error code.
- **Status:** Implemented.

---

#### `func ERRNO feof(FILE^ fd)` *(partial)*

Returns `BOOL.TRUE` if the end-of-file flag is set in the `FILE` struct.

---

#### `func ERRNO ferror(FILE^ fd)`

Returns the last error code stored in `fd^.error`.

---

#### `func ERRNO rewind(FILE^ fd)` *(stub)*

Calls `fseek(fd, 0, SEEK_SET)` — currently returns `ERRNO.ENODEV` as fseek is not implemented.

---

#### `func word fread(FILE^ fd, byte^ buffer, word size, word count)` *(TODO)*

Not yet implemented. Returns 0.

---

#### `func ERRNO fseek(FILE^ fd, long offset, byte whence)` *(TODO)*

Not yet implemented. Returns `ERRNO.ENODEV`.

---

#### `func long ftell(FILE^ fd)` *(TODO)*

Not yet implemented. Returns 0.

---

#### `func byte fgetc(FILE^ fd)` *(TODO)*

Not yet implemented. Returns 0 and sets `fd^.error = ERRNO.ENODEV`.

---

#### `func byte fputc(FILE^ fd, byte ch)` *(TODO)*

Not yet implemented. Returns 0 and sets `fd^.error = ERRNO.ENODEV`.

---

#### `func ERRNO rename(FILE^ fd, const byte^ oldname, const byte^ newname)` *(TODO)*

Not yet implemented. Returns `ERRNO.ENODEV`.

---

#### `func ERRNO remove(byte^ filename)` *(TODO)*

Not yet implemented. Returns `ERRNO.ENODEV`.

---

#### Formatted I/O *(TODO)*

The following functions are declared but not yet implemented (return 0 and set `fd^.error = ERRNO.ENODEV`):

- `func byte fprintf(FILE^ fd, const byte^ format, word arg1..arg8)`
- `func byte fputs(FILE^ fd, const byte^ str)`
- `func byte fscanf(FILE^ fd, const byte^ format, word arg1..arg8)`

---

### Internal / Low-Level

These symbols are exported but intended for internal library use:

#### `func byte CIO(byte ch, byte command, word adr=0, word len=0, byte aux1=0, byte aux2=0, byte aux3=0)`

Low-level CIO dispatcher. Sets up the IOCB for channel `ch` and calls the CIO handler at `$E456`. Use the higher-level `fopen`/`fclose`/`fwrite` wrappers instead.

> When compiled with `.define DEBUG_CIO`, prints CIO call parameters and status to the screen.

#### `func byte find_free_IOCB()`

Scans IOCB channels 3–7 for a free slot (`ICHID == 255`). Returns the channel number or 255 if none is free.

#### `proc CONSTRUCTOR()` *(#noexport)*

Module initializer — automatically called by the compiler at program startup. Builds the `vlstart[]` line-pointer table from the screen base address and clears the screen.

#### `proc atari_file_data_area()` *(#keep #noexport)*

Emits the Atari COM file header (`COMHEADER` segment) and optional `AUTOSTRT` segment (when `-D AUTOSTART` is defined). Required by the linker; never call directly.

---

## Hardware Definition Files

These files define Atari hardware chip registers as port-mapped structs. They have **no `.module` declaration** and are included directly into modules that need hardware access.

### atari_gtia.zap — GTIA Chip

**File:** `work/lib/atari/atari_gtia.zap`
**Platform:** Atari 8-bit
**Depends:** nothing

Defines register layouts for the CTIA/GTIA (Color Television Interface Adapter / Graphics Television Interface Adapter) chip at `$D000`. Handles sprites (players/missiles), color registers, collision detection, and console buttons.

#### `GTIA_RD_struct #port #RD` — Read registers at `$D000`

| Offset | Field | Description |
|--------|-------|-------------|
| `$00–$03` | `M0PF–M3PF` | Missile 0–3 vs. playfield collision bits |
| `$04–$07` | `P0PF–P3PF` | Player 0–3 vs. playfield collision bits |
| `$08–$0B` | `M0PL–M3PL` | Missile 0–3 vs. player collision bits |
| `$0C–$0F` | `P0PL–P3PL` | Player 0–3 vs. player collision bits |
| `$10–$13` | `TRIG0–TRIG3` | Joystick triggers (0=pressed) |
| `$14` | `PAL` | PAL/NTSC indicator |
| `$22` | `CONSOL` | Console button state (Start/Select/Option) |

#### `GTIA_WR_struct #port #WR` — Write registers at `$D000`

| Offset | Field | Description |
|--------|-------|-------------|
| `$00–$03` | `HPOSP0–HPOSP3` | Player 0–3 horizontal position |
| `$04–$07` | `HPOSM0–HPOSM3` | Missile 0–3 horizontal position |
| `$08–$0B` | `SIZEP0–SIZEP3` | Player 0–3 size (1×/2×/4× width) |
| `$0C` | `SIZEM` | Missile sizes (2 bits each) |
| `$0D–$10` | `GRAFP0–GRAFP3` | Player 0–3 graphics data |
| `$11` | `GRAFM` | Missile graphics data |
| `$12–$15` | `COLPM0–COLPM3` | Player/missile 0–3 color+luminance |
| `$16–$19` | `COLPF0–COLPF3` | Playfield 0–3 color+luminance |
| `$1A` | `COLBK` | Background color+luminance |
| `$1B` | `PRIOR` | Sprite/playfield priority |
| `$1C` | `VDELAY` | Vertical delay for missiles/players |
| `$1D` | `GRACTL` | Enable DMA for players/missiles |
| `$1E` | `HITCLR` | Clear all collision registers |
| `$1F` | `CONSOL` | Sound/speaker control |

Hardware instances:
```zap
GTIA_RD_struct GTIA_RD @$D000   ; read from this struct
GTIA_WR_struct GTIA_WR @$D000   ; write to this struct
```

#### Shadow Registers (OS RAM)

| Name | Address | Description |
|------|---------|-------------|
| `PCOLR0–PCOLR3` | `704–707` | Player/missile 0–3 color shadows |
| `COLOR0–COLOR4` | `708–712` | Playfield 0–3 + background color shadows |
| `M0COLOR–M3COLOR` | `713–716` | Missile 0–3 color shadows |
| `GPRIOR` | `717` | Graphics priority shadow |

#### Color Constants

16 base hue values (add 2–14 in steps of 2 for brightness):

| Constant | Value | Color |
|----------|-------|-------|
| `COLOR_BLACK` | `$00` | Black |
| `COLOR_RUST` | `$10` | Rust |
| `COLOR_RED_ORANGE` | `$20` | Red-orange |
| `COLOR_DARK_ORANGE` | `$30` | Dark orange |
| `COLOR_RED` | `$40` | Red |
| `COLOR_DARK_LAVENDER` | `$50` | Dark lavender |
| `COLOR_COBALT_BLUE` | `$60` | Cobalt blue |
| `COLOR_ULTRAMARINE` | `$70` | Ultramarine |
| `COLOR_MEDIUM_BLUE` | `$80` | Medium blue |
| `COLOR_DARK_BLUE` | `$90` | Dark blue |
| `COLOR_BLUE_GREY` | `$A0` | Blue-grey |
| `COLOR_OLIVE_GREEN` | `$B0` | Olive green |
| `COLOR_MEDIUM_GREEN` | `$C0` | Medium green |
| `COLOR_DARK_GREEN` | `$D0` | Dark green |
| `COLOR_ORANGE_GREEN` | `$E0` | Orange-green |
| `COLOR_ORANGE` | `$F0` | Orange |

Example — set background to medium blue, brightness 8:
```zap
.include "lib/atari/atari_gtia.zap"
COLOR4 = COLOR_MEDIUM_BLUE + 8
```

---

### atari_pokey.zap — POKEY Chip

**File:** `work/lib/atari/atari_pokey.zap`
**Platform:** Atari 8-bit
**Depends:** nothing

Defines register layouts for the POKEY (Programmable Operator Keyboard Interface Expression) chip at `$D200`. Handles 4-channel sound synthesis, keyboard scanning, paddle/joystick input, and serial I/O.

#### `POKEY_RD_struct #port #RD` — Read registers at `$D200`

| Offset | Field | Description |
|--------|-------|-------------|
| `$00–$07` | `POT0–POT7` | Potentiometer (paddle) inputs |
| `$08` | `ALLPOT` | Potentiometer port status |
| `$09` | `KBCODE` | Keyboard scan code |
| `$0A` | `RANDOM` | Random number generator output |
| `$0D` | `SERIN` | Serial port input |
| `$0E` | `IRQST` | IRQ interrupt status |
| `$0F` | `SKSTAT` | Serial/keyboard status |

#### `POKEY_WR_struct #port #WR` — Write registers at `$D200`

| Offset | Field | Description |
|--------|-------|-------------|
| `$00,$02,$04,$06` | `AUDF1–AUDF4` | Audio channel 1–4 frequency |
| `$01,$03,$05,$07` | `AUDC1–AUDC4` | Audio channel 1–4 control |
| `$08` | `AUDCTL` | Audio control (clock, filter, poly) |
| `$09` | `STIMER` | Start timers |
| `$0A` | `SKRES` | Reset SKSTAT status |
| `$0B` | `POTGO` | Start potentiometer scan |
| `$0C` | `SEROUT` | Serial port output |
| `$0D` | `IRQEN` | IRQ interrupt enable |
| `$0E` | `SKCTL` | Serial/keyboard control |

Hardware instances:
```zap
POKEY_WR_struct POKEY_WR @$D200
POKEY_RD_struct POKEY_RD @$D200
```

#### Shadow Registers (OS RAM)

| Name | Address | Description |
|------|---------|-------------|
| `PADDL0–PADDL7` | `624–631` | Paddle 0–7 position (0–228) |
| `STICK0–STICK3` | `632–635` | Joystick 0–3 direction bits |
| `PTRIG0–PTRIG7` | `636–643` | Paddle trigger 0–7 (0=pressed) |
| `STRIG0–STRIG3` | `644–647` | Joystick trigger 0–3 (0=pressed) |

Example — play a tone on channel 1:
```zap
.include "lib/atari/atari_pokey.zap"
POKEY_WR.AUDF1 = 100    ; frequency
POKEY_WR.AUDC1 = $A8    ; pure tone, volume 8
```

---

### PIA.zap — PIA Chip

**File:** `work/lib/atari/PIA.zap`
**Platform:** Atari 8-bit
**Depends:** nothing

Defines register layout for the PIA (Motorola 6520 Peripheral Interface Adapter) chip at `$D300`. Provides two 8-bit bidirectional I/O ports (A and B) with individual control registers.

#### `PIA_RD_struct #port` — Registers at `$D300`

| Offset | Field | Description |
|--------|-------|-------------|
| `$00` | `PORTA` | Port A — joystick directions (bits 0–7) |
| `$01` | `PORTB` | Port B — XL/XE bank-switching and OS/BASIC control |
| `$02` | `PACTL` | Port A control register |
| `$03` | `PBCTL` | Port B control register |

Hardware instance:
```zap
PIA_RD_struct PIA @$D300
```

Example — read joystick 0 direction:
```zap
.include "lib/atari/PIA.zap"
byte joy = PIA.PORTA & $0F   ; lower nibble = joystick 0
```

On Atari XL/XE, `PORTB` controls OS ROM bank-switching and the built-in BASIC ROM enable/disable.

---

## Implementation Status Matrix

| Module / File | Exports | Status |
|---------------|---------|--------|
| `errno.zap` | `ERRNO` enum (76 values) | Complete |
| `types.zap` | `BOOL`, `FILE`, `SEEK`, `NULL`, `FILE_HANDLE_MAX` | Complete |
| `string.zap` | `memchr`, `memcmp`, `strlen`, `strncmp`, `strnchr`, `memcpy`, `memmove`, `memset`, `strncat`, `strncpy` | Complete |
| `stdio.zap` | Platform coordinator + `CONSTRUCTOR` | Complete (stub) |
| `atari_stdio.zap` — screen I/O | `cls`, `putchar`, `puts`, `crlf`, `gotoxy`, `cursor_on/off`, `putx`, `printb`, `ascii_to_screen` | Complete |
| `atari_stdio.zap` — keyboard | `getchar`, `getc`, `getcblink`, `gets`, `delay` | Complete |
| `atari_stdio.zap` — file I/O | `fopen`, `fclose`, `fwrite`, `feof`, `ferror`, `rewind` | Partial |
| `atari_stdio.zap` — file I/O | `fread`, `fseek`, `ftell`, `fgetc`, `fputc`, `rename`, `remove` | TODO |
| `atari_stdio.zap` — formatted I/O | `fprintf`, `fputs`, `fscanf` | TODO |
| `atari_gtia.zap` | `GTIA_RD/WR` structs, shadow regs, color constants | Complete |
| `atari_pokey.zap` | `POKEY_RD/WR` structs, shadow regs | Complete |
| `PIA.zap` | `PIA` struct | Complete |

---

## Usage Examples

### Hello World (Atari)

```zap
.include "lib/stdio.zap"

proc main()
    cls()
    puts("Hello, World!\n")
end
```

Compile:
```
zapc hello.zap -D ATARI -6502 -o hello.s
```

---

### String operations

```zap
.include "lib/string.zap"

proc main()
    byte buf[32]
    memset(buf, 0, 32)
    strncpy(buf, "ZAP!", 5)
    ; buf now contains "ZAP!\0"
    byte len = strlen(buf)    ; len = 4
end
```

---

### Reading a key with blinking cursor

```zap
.include "lib/stdio.zap"

proc main()
    byte ch
    puts("Press a key: ")
    ch = getcblink()
    puts("\nYou pressed: ")
    putchar(ch)
    crlf()
end
```

---

### Writing a file to disk

```zap
.include "lib/stdio.zap"

proc main()
    FILE f
    byte result

    result = fopen(@f, "D:TEST.TXT", ICAX1_Mode.Write)
    if result == ERRNO.OK
        fwrite(@f, "Hello from ZAP!\n", 16)
        fclose(@f)
        puts("File written.\n")
    else
        puts("Error opening file.\n")
    end
end
```

---

### Controlling POKEY audio

```zap
.include "lib/atari/atari_pokey.zap"

proc main()
    ; Play a tone on channel 1
    POKEY_WR.AUDF1 = 80     ; frequency (lower = higher pitch)
    POKEY_WR.AUDC1 = $A8    ; pure tone, volume 8
    POKEY_WR.AUDCTL = 0     ; standard clock

    ; ... do something ...

    ; Silence
    POKEY_WR.AUDC1 = 0
end
```

---

### Sprite positioning with GTIA

```zap
.include "lib/atari/atari_gtia.zap"

proc main()
    ; Position player 0 sprite at horizontal position 80
    GTIA_WR.HPOSP0 = 80
    ; Set its color to red (luminance 10)
    COLOR0 = COLOR_RED + 10
end
```
