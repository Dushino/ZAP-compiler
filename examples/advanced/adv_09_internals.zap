; Example: adv_09_internals.zap
; Source: ADVANCED_TOPICS.md, section "Compiler Internals" (lines 1336-1459)
;
; Demonstrates: binary/hex number literals, array access patterns

; --- Number Literals ---
byte b1 = %10101010     ; Binary (percent prefix)
byte h1 = $FF           ; Hex (dollar sign)
byte d1 = 255           ; Decimal

; --- Array Access Pattern ---
byte arr[5]
byte index = 2

proc main()
    byte value = arr[index]  ; Compiles to base + index addressing
    arr[0] = 10
    arr[1] = 20
    arr[2] = 30
    arr[3] = 40
    arr[4] = 50
    value = arr[index]       ; value = 30
end
