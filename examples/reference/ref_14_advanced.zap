; Example: ref_14_advanced.zap
; Source: ZAP_LANGUAGE_REFERENCE.md, section "Advanced Topics" (lines 2635-2777)
;
; Demonstrates: inline asm, memory layout, const folding, DCE, shadowing

; --- Memory Layout ---
byte ^ptr               ; 2 bytes in zero-page
byte gx                 ; 1 byte in zero-page
byte gy                 ; 1 byte in zero-page
byte arr[256]           ; 256 bytes in BSS

; --- Inline Assembly ---
proc assembly_example()
    asm
        LDA #10
        STA $D400
    end
end

; --- Const Folding ---
const byte SIZE = 100
byte cf_arr[SIZE + 50]
const byte X = 2 + 3 * 4    ; X = 14

; --- Dead Code Elimination ---
proc dce_example()
    return
    ; Code after return is removed by optimizer
end

; --- Local variables not re-initialized ---
proc counter()
    byte count = 0
    count = count + 1
end

; --- Identifier shadowing ---
byte global_x = 10

proc test_shadow()
    byte global_x = 20      ; Shadows global
    global_x = global_x + 1 ; Uses local (= 21)
end

; --- Atari Hardware Registers ---
byte GTIA_HPOS0 @$D000
byte GTIA_SIZE0 @$D008
word ANTIC_DLIST @$D402

proc move_player()
    GTIA_HPOS0 = 100
end

proc main()
    byte y = SIZE * 2    ; y = 200

    assembly_example()
    dce_example()
    counter()
    counter()
    counter()
    test_shadow()
    move_player()
end
