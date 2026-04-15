---
nav_order: 5
---

# ZAP! Standard Library Reference

The author of this software stands in solidarity with 🇺🇦 Ukraine. 
We believe in a world where international borders are respected and human rights are upheld. 
We encourage all users of this software to contribute to humanitarian efforts in 🇺🇦 Ukraine.


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

Defines the `ERRNO` enum with Atari CIO status byte values. `OK = 0` is the API-level success code. The `CIO()` function remaps all raw CIO success statuses (bit 7 clear, `$01`–`$7F`) to `ERRNO.OK`. Error statuses (bit 7 set, `$80`–`$FF`) pass through as-is and map directly to the enum values below.

### Enum `ERRNO`

| Value | Code | Meaning |
|-------|------|---------|
| 0 | `OK` | No error (API level) |
| 1 | `SUCCESS` | Operation complete (raw CIO) |
| 128 | `BRK_KEY` | BREAK key abort |
| 129 | `IOCB_IN_USE` | IOCB already in use (open) |
| 130 | `NONEXISTENT_DEV` | Non-existent device |
| 131 | `WRITE_ONLY` | Opened for write only |
| 132 | `INVALID_CMD` | Invalid command |
| 133 | `NOT_OPEN` | Device or file not open |
| 134 | `INVALID_IOCB` | Invalid IOCB number |
| 135 | `READ_ONLY` | Opened for read only |
| 136 | `EOF` | End of file |
| 137 | `TRUNCATED` | Truncated record |
| 138 | `TIMEOUT` | Device timeout |
| 139 | `NAK` | Device NAK |
| 140 | `FRAMING_ERR` | Serial bus input framing error |
| 141 | `CURSOR_RANGE` | Cursor out of range |
| 142 | `OVERRUN` | Serial bus data frame overrun error |
| 143 | `CHECKSUM` | Serial bus data frame checksum error |
| 144 | `DEVICE_ERR` | Device done error |
| 145 | `BAD_MODE` | Bad screen mode |
| 146 | `NOT_SUPPORTED` | Function not supported by handler |
| 147 | `NO_MEMORY` | Insufficient memory for screen mode |
| 160 | `DRIVE_ERR` | Disk drive # error |
| 161 | `TOO_MANY_FILES` | Too many open disk files |
| 162 | `DISK_FULL` | Disk full |
| 163 | `DISK_IO_ERR` | Fatal disk I/O error |
| 164 | `FILE_MISMATCH` | Internal file # mismatch |
| 165 | `BAD_FILENAME` | File name error |
| 166 | `POINT_LENGTH` | Point data length error |
| 167 | `FILE_LOCKED` | File locked |
| 168 | `INVALID_DISK_CMD` | Command invalid for disk |
| 169 | `DIR_FULL` | Directory full (64 files) |
| 170 | `FILE_NOT_FOUND` | File not found |
| 171 | `POINT_INVALID` | Point invalid |

> **Note:** `ERRNO.SUCCESS` (1) is the raw CIO "operation complete" status. Application code should compare against `ERRNO.OK` (0), which is the remapped API-level success code returned by all library functions.

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

### Enum `KEY` — Keyboard Key Codes

ATASCII key codes for special keys, used with `getchar()`, `getcblink()`, and `gets()`:

| Value | Name | Key |
|-------|------|-----|
| `$9B` | `Key.ENTER` | Return / Enter |
| `$1E` | `Key.LEFT` | Left arrow |
| `$1F` | `Key.RIGHT` | Right arrow |
| `$1C` | `Key.UP` | Up arrow |
| `$1D` | `Key.DOWN` | Down arrow |
| `$2B` | `Key.CTRL_LEFT` | Ctrl+Left |
| `$2A` | `Key.CTRL_RIGHT` | Ctrl+Right |
| `$2D` | `Key.CTRL_UP` | Ctrl+Up |
| `$3D` | `Key.CTRL_DOWN` | Ctrl+Down |
| `$7D` | `Key.HOME` | Clear/Home |
| `$FE` | `Key.DELETE` | Delete |
| `$FF` | `Key.INSERT` | Insert |
| `$7E` | `Key.BACKSPACE` | Backspace |
| `$1B` | `Key.ESCAPE` | Escape |

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
| `$07` | `GetChr` | Read character(s) / buffer |
| `$0B` | `PutChr` | Write character(s) / buffer |
| `$05` | `GetRec` | Read record (line) |
| `$09` | `PutRec` | Write record (line) |
| `$0D` | `Status` | Get device status |
| `$20` | `Rename` | Rename file (DOS 2.5) |
| `$21` | `Delete` | Delete file (DOS 2.5) |

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

Prints a byte (0–255) as a 3-digit decimal number. Uses the shared BCD conversion engine (6502 decimal mode).

- `lzero=1` — show leading zeros (e.g., `007`); `0` = suppress leading zeros
- `ralign=1` — right-align by padding spaces on the left; `0` = no padding

```zap
printb(score)           ; "042" (default: leading zeros, right-align)
printb(score, 0, 0)     ; "42"  (no leading zeros, no padding)
```

---

#### `proc printw(word arg, const byte lzero=1, const byte ralign=1)`

Prints a word (0–65535) as a 5-digit decimal number. Uses the shared BCD conversion engine.

- `lzero=1` — show leading zeros (e.g., `01234`); `0` = suppress
- `ralign=1` — right-align with spaces; `0` = no padding

```zap
printw(total)           ; "01234" (default)
printw(total, 0, 0)     ; "1234"  (no leading zeros, no padding)
```

---

#### `proc printl(long arg, const byte lzero=1, const byte ralign=1)`

Prints a long (0–4294967295) as a 10-digit decimal number. Uses the shared BCD conversion engine.

- `lzero=1` — show leading zeros; `0` = suppress
- `ralign=1` — right-align with spaces; `0` = no padding

```zap
printl(big_value, 0, 0)   ; "123456789" (no leading zeros)
```

---

#### `proc putxw(word value)`

Prints a word as four uppercase hexadecimal characters (e.g., `$1A2B` → `"1A2B"`). Calls `putx()` twice for high and low bytes.

```zap
putxw(address)    ; e.g. "D200"
```

---

#### BCD Conversion Engine (Internal)

All three `printb`/`printw`/`printl` functions share a single BCD conversion routine (`print_convert`, `#noexport`) that uses the 6502 decimal mode (`SED`) double-dabble algorithm. This converts a 32-bit binary value to 10 packed BCD digits in a fixed 32-iteration loop (~960 cycles), regardless of the value. The shared `print_decimal` proc handles leading-zero suppression and right-alignment.

Total memory cost: ~19 bytes shared variables + ~60 bytes ASM conversion + ~40 bytes output logic. Each `printb`/`printw`/`printl` wrapper adds only ~20–30 bytes.

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

File I/O uses the Atari CIO system. Each open file occupies one IOCB channel (channels 1–7 are available; 0 is the screen editor). The low-level `CIO()` function handles all IOCB setup and status remapping.

#### CIO Status Handling

The `CIO()` function reads the status from the Y register after `jsr $E456`. All success statuses (bit 7 clear, `$01`–`$7F`) are remapped to `ERRNO.OK` (0). Error statuses (bit 7 set, `$80`–`$FF`) pass through as-is and map directly to `ERRNO` enum values (e.g., 136 = `ERRNO.EOF`).

**EOF behaviour:** Only read functions (`fread`, `fgetc`) check and set the `fd^.eof` flag via `checkeof()`. Write functions (`fwrite`, `fputc`, `fputs`) do not touch the EOF flag — this matches POSIX/C semantics where `feof()` only reflects read operations. Write errors (e.g., disk full) are reported via `fd^.error` / `ferror()`.

---

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

- **Returns:** `ERRNO.OK` on success, `ERRNO.NOT_OPEN` if `fd` is NULL.

---

#### `func byte fread(FILE^ fd, byte^ buffer, word size)`

Reads up to `size` bytes from the open file into `buffer` using CIO `GetChr`.

- **Returns:** `ERRNO.OK` on success, or a CIO error code.
- Sets `fd^.eof = BOOL.TRUE` if end-of-file is reached during the read.

---

#### `func word fwrite(FILE^ fd, byte^ buffer, word size)`

Writes `size` bytes from `buffer` to the open file using CIO `PutChr`.

- **Returns:** `ERRNO.OK` on success, or a CIO error code.
- Does **not** set `fd^.eof` (write operations never trigger EOF).

---

#### `func byte fgetc(FILE^ fd)`

Reads a single byte from the open file. Uses `cio_char` as a 1-byte buffer passed to CIO (the accumulator is unreliable on EOF).

- **Returns:** the character read on success or EOF, `0` on error.
- Sets `fd^.eof = BOOL.TRUE` when EOF is reached.
- On EOF, the last valid byte is still returned (Atari CIO delivers the final byte together with the EOF status).

```zap
byte ch = fgetc(@myfile)
if feof(@myfile) == BOOL.TRUE
    ; end of file reached
end
```

---

#### `func ERRNO fputc(FILE^ fd, byte ch)`

Writes a single byte to the open file. Uses `cio_char` as a 1-byte buffer passed to CIO `PutChr` with length 1.

- **Returns:** `ERRNO.OK` on success, or a CIO error code.

---

#### `func ERRNO fputs(FILE^ fd, const byte^ str)`

Writes a null-terminated string to the open file using CIO `PutChr` with `strlen(str)` as buffer length.

- **Returns:** `ERRNO.OK` on success, or a CIO error code.

---

#### `func BOOL feof(FILE^ fd)`

Returns `BOOL.TRUE` if the end-of-file flag is set in the `FILE` struct. Only read operations (`fread`, `fgetc`) set this flag.

- **Returns:** `BOOL.TRUE` or `BOOL.FALSE`, `ERRNO.NOT_OPEN` if `fd` is NULL.

---

#### `func ERRNO ferror(FILE^ fd)`

Returns the last error code stored in `fd^.error`.

- **Returns:** `ERRNO.OK` if no error, or the last CIO error code. `ERRNO.NOT_OPEN` if `fd` is NULL.

---

#### `func ERRNO rename(const byte^ oldname, const byte^ newname)`

Renames a file using CIO Rename command. Concatenates `oldname,newname` into a single buffer (max 32 characters) as required by Atari DOS.

- **Returns:** `ERRNO.OK` on success, `ERRNO.TOO_MANY_FILES` if no free IOCB, `ERRNO.BAD_FILENAME` if combined name too long, or a CIO error code.

---

#### `func ERRNO remove(byte^ filename)`

Deletes a file using CIO Delete command.

- **Returns:** `ERRNO.OK` on success, `ERRNO.TOO_MANY_FILES` if no free IOCB, or a CIO error code.

---

#### Formatted I/O *(TODO)*

The following function is declared but not yet implemented (returns 0 and sets `fd^.error = ERRNO.NOT_SUPPORTED`):

- `func byte fscanf(FILE^ fd, const byte^ format, word arg1..arg8)`

---

### Internal / Low-Level

These symbols are exported but intended for internal library use:

#### `func byte CIO(byte ch, byte command, word adr=0, word len=0, byte aux1=0, byte aux2=0)`

Low-level CIO dispatcher. Sets up the IOCB for channel `ch` (masked to 0–7) and calls the CIO handler at `$E456`. After the call, the accumulator is saved in `cio_char` (module-level byte, `#noexport`) and the Y register status is used as the return value. All success statuses (bit 7 clear) are remapped to `ERRNO.OK`; error statuses pass through as-is.

Use the higher-level `fopen`/`fclose`/`fread`/`fwrite`/`fgetc`/`fputc`/`fputs` wrappers instead of calling `CIO()` directly.

#### `func byte find_free_IOCB()`

Scans IOCB channels 1–7 for a free slot (`ICHID == 255`). Returns the channel number or 255 if none is free.

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
