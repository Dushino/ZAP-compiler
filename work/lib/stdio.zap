; ============================================================
; Module: stdio
; File:   lib/stdio.zap
; Platform: Multi-platform (conditional)
; Depends:  errno, types
;
; Description:
;   Platform I/O coordinator.  Selects the correct platform-specific
;   I/O implementation at compile time via preprocessor symbols:
;
;     -D ATARI  ->  includes lib/atari/atari_stdio.zap
;     -D SBC    ->  includes lib/sbc/sbc_stdio.zap  (not yet implemented)
;
;   All I/O functions (putchar, puts, getchar, fopen, …) are provided
;   by the included platform file and become part of this module's
;   exported namespace.
;
; Exports (own):
;   proc CONSTRUCTOR()  -- module init stub (empty; actual init in platform file)
;
; Built-in commands (compiler-generated, no library function needed):
;   POKE(addr, value)   -- write byte to memory address (inline code)
;   PEEK(addr)          -- read byte from memory address (inline code, returns BYTE)
;
; Status: Complete (platform selection); platform implementations vary
; ============================================================

.module "stdio"

.include "errno.zap"
.include "types.zap"


proc CONSTRUCTOR()
    ; initialization code for stdio module, if needed
end


; if no platform defined, default to ATARI (for testing)
.ifndef ATARI 
    .ifndef SBC
        .define ATARI
    .endif
.endif    


.ifdef ATARI
    .include "./atari/atari_stdio.zap"
.endif

.ifdef SBC
    .include "./sbc/sbc_stdio.zap"   
.endif


; ---- Shared BCD decimal print engine ----
; Used by printb, printw, printl. Converts a 32-bit binary value
; to decimal ASCII digits using 6502 decimal mode (double-dabble).

byte print_bin[4]    #noexport   ; 32-bit binary input (little-endian)
byte print_bcd[5]    #noexport   ; packed BCD output (10 digits)
byte print_buf[10]   #noexport   ; unpacked ASCII digits (MSB first)


/*
    putx - print HEX BYTE value as two characters
*/
proc putx(byte value)
    const byte hex_digits[] = "0123456789ABCDEF"

    putchar(hex_digits[value >> 4])
    putchar(hex_digits[value & $0F])
end


/*
    putxw - print word as 4 hex digits (e.g. $1A2B -> "1A2B")
*/
proc putxw(word value)
    putx(HIGH(value))
    putx(LOW(value))
end


/*
    print_convert - convert 32-bit binary in print_bin to ASCII digits in print_buf
    Uses 6502 decimal mode (SED) for BCD double-dabble conversion.
*/
proc print_convert() #noexport
    byte i, k

    asm
        sed                         ; enable BCD mode
        lda #$00
        sta _PRINT_BCD
        sta _PRINT_BCD+1
        sta _PRINT_BCD+2
        sta _PRINT_BCD+3
        sta _PRINT_BCD+4

        ldx #32                     ; 32 bits to process
__ZAP_bcd_loop:
        asl _PRINT_BIN              ; shift MSB out of binary value
        rol _PRINT_BIN+1
        rol _PRINT_BIN+2
        rol _PRINT_BIN+3

        lda _PRINT_BCD              ; shift carry into BCD (decimal add)
        adc _PRINT_BCD
        sta _PRINT_BCD
        lda _PRINT_BCD+1
        adc _PRINT_BCD+1
        sta _PRINT_BCD+1
        lda _PRINT_BCD+2
        adc _PRINT_BCD+2
        sta _PRINT_BCD+2
        lda _PRINT_BCD+3
        adc _PRINT_BCD+3
        sta _PRINT_BCD+3
        lda _PRINT_BCD+4
        adc _PRINT_BCD+4
        sta _PRINT_BCD+4

        dex
        bne __ZAP_bcd_loop
        cld                         ; restore binary mode
    end

    ; Unpack packed BCD to ASCII digits (MSB first)
    k = 0
    i = 5
    while i > 0
        i -= 1
        print_buf[k] = (print_bcd[i] >> 4) + '0'
        k += 1
        print_buf[k] = (print_bcd[i] & $0F) + '0'
        k += 1
    end
end


/*
    print_decimal - shared output routine for printb/printw/printl
    Handles leading zero suppression and right-alignment padding.
    digits: number of digits to display (3 for byte, 5 for word, 10 for long)
*/
proc print_decimal(const byte digits, const byte lzero, const byte ralign) #noexport
    byte i, j
    byte start

    start = 10 - digits

    ; Find first non-zero digit (skip leading zeros)
    if !lzero
        i = start
        while i < 9
            if print_buf[i] != '0'
                break
            end
            i += 1
        end
    else
        i = start
    end

    ; Right-align: pad with spaces
    if ralign
        j = start
        while j < i
            putchar(' ')
            j += 1
        end
    end

    ; Print digits
    while i < 10
        putchar(print_buf[i])
        i += 1
    end
end


/*
    printb - print byte (0-255) as decimal with optional leading zeros and right-alignment
    lzero=1: show leading zeros (e.g. "042"), lzero=0: suppress (e.g. "42")
    ralign=1: right-align with spaces (e.g. "  7"), ralign=0: no padding
*/
proc printb(byte arg, const byte lzero=1, const byte ralign=1)
    print_bin[0] = arg
    print_bin[1] = 0
    print_bin[2] = 0
    print_bin[3] = 0
    print_convert()
    print_decimal(3, lzero, ralign)
end


/*
    printw - print word (0-65535) as decimal with optional leading zeros and right-alignment
*/
proc printw(word arg, const byte lzero=1, const byte ralign=1)
    asm
        lda _PRINTW_ARG
        sta _PRINT_BIN
        lda _PRINTW_ARG+1
        sta _PRINT_BIN+1
    end
    print_bin[2] = 0
    print_bin[3] = 0
    print_convert()
    print_decimal(5, lzero, ralign)
end


/*
    printl - print long (0-4294967295) as decimal with optional leading zeros and right-alignment
*/
proc printl(long arg, const byte lzero=1, const byte ralign=1)
    asm
        lda _PRINTL_ARG
        sta _PRINT_BIN
        lda _PRINTL_ARG+1
        sta _PRINT_BIN+1
        lda _PRINTL_ARG+2
        sta _PRINT_BIN+2
        lda _PRINTL_ARG+3
        sta _PRINT_BIN+3
    end
    print_convert()
    print_decimal(10, lzero, ralign)
end


