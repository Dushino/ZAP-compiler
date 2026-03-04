; Test character literals: single-char 'x' produces a BYTE value (ASCII code)
; Multi-char literals ('a''b') are NOT supported — use $hex for word/long values.

byte result @40000 = 0

proc main()
    byte a = 'a'                    ; $61 = 97
    byte b = 'b'                    ; $62 = 98
    word w = $6261                  ; equivalent of what 'a''b' used to produce
    byte low = w & $FF              ; $61
    byte high = (w >> 8) & $FF      ; $62
    result = low + high             ; 0x61 + 0x62 = 97 + 98 = 195 = $C3
end
