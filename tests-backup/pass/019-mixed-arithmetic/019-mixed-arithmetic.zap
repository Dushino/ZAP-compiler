; mixed arithmetic - testing type conversions


byte result11 @40000
byte result12 @40001
byte result13 @40002

word result21 @40008
word result22 @40010
word result23 @40012

byte result14 @40016
byte result15 @40017

word result24 @40018
word result25 @40020
word result26 @40022


proc main()
    ; Basic arithmetic with BYTE operands → BYTE result
    result11 = 2 + 3 * 4            ; Should be $0e (2 + 12 = 14)
    result12 = 10 - 2 * 3           ; Should be $04 (10 - 6 = 4)
    result13 = 100 / 5 + 2          ; Should be $16 (20 + 2 = 22)

    ; Basic arithmetic with WORD operands → WORD result
    result21 = 260 + 258 * 4        ; Should be $050c (260 + 1032 = 1292)
    result22 = 8191 - 258 * 3       ; Should be $1cf9 (8191 - 774 = 7417)
    result23 = 8191 / 5 + 2         ; Should be $0668 (1638 + 2 = 1640)

    ; WORD * BYTE → BYTE (truncate to low byte)
    result14 = result21 * 3         ; Should be $24 (0x050c * 3 = 0x0f24, take low byte)
    
    ; BYTE + BYTE → BYTE (truncate if overflow)
    result15 = result12 + $20       ; Should be $24 (4 + 32 = 36)

    ; BYTE * BYTE → WORD (full result)
    result24 = result11 * $31       ; Should be $02AE (14 * 49 = 686)
    
    ; BYTE + BYTE → WORD (zero-extend sum)
    result25 = result12 + $123      ; Should be $0127 (4 + 291 = 295)
    
    ; WORD - BYTE → WORD
    result26 = result21 - $40       ; Should be $04cc (0x050c - 0x40 = 0x04cc)

end
