; printb / printw / printl / putxw — decimal and hex print functions
; Tests compilation with all argument combinations and BCD ASM block

byte print_bin[4]
byte print_bcd[5]

proc putchar(byte ch)
end

proc putx(byte value)
end

; Test BCD conversion ASM block (verifies globals referenced only from ASM survive DCE)
proc bcd_convert()
    asm
        sed
        lda #$00
        sta _PRINT_BCD
        sta _PRINT_BCD+1
        sta _PRINT_BCD+2
        sta _PRINT_BCD+3
        sta _PRINT_BCD+4
        ldx #32
__ZAP_bcd_207:
        asl _PRINT_BIN
        rol _PRINT_BIN+1
        rol _PRINT_BIN+2
        rol _PRINT_BIN+3
        lda _PRINT_BCD
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
        bne __ZAP_bcd_207
        cld
    end
end

proc printb(byte arg, const byte lzero=1, const byte ralign=1)
    print_bin[0] = arg
    print_bin[1] = 0
    print_bin[2] = 0
    print_bin[3] = 0
    bcd_convert()
end

proc printw(word arg, const byte lzero=1, const byte ralign=1)
    bcd_convert()
end

proc printl(long arg, const byte lzero=1, const byte ralign=1)
    bcd_convert()
end

proc putxw(word value)
end


proc main()
    byte  b = 42
    word  w = 12345
    long  l = 1000000

    ; --- printb: all argument combinations ---
    printb(b)
    printb(b, 0)
    printb(b, 0, 0)
    printb(b, 1, 0)
    printb(0)
    printb(255)

    ; --- printw: all argument combinations ---
    printw(w)
    printw(w, 0)
    printw(w, 0, 0)
    printw(0)
    printw(65535)

    ; --- printl: all argument combinations ---
    printl(l)
    printl(l, 0)
    printl(l, 0, 0)
    printl(0)

    ; --- putx / putxw ---
    putx(b)
    putxw(w)
    putxw(0)
    putxw($ABCD)
end
