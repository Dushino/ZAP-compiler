; Test: Negative literal constants
;
; Purpose: Validates that negative integer literals wrap correctly in two's
;          complement for BYTE and WORD types.
;
; Expected results at $0200:
;   $0200: $FB (251) = -5 as byte
;   $0201: $FF (255) = -1 as byte
;   $0202: $80 (128) = -128 as byte (minimum signed byte)
;   $0203: $FB (251) = 0 - 5 via runtime subtraction (same as -5)

byte result1 @$0200 = 0
byte result2 @$0201 = 0
byte result3 @$0202 = 0
byte result4 @$0203 = 0

proc main()
    byte a = -5        ; two's complement byte: 256 - 5 = 251 = $FB
    byte b = -1        ; two's complement byte: 256 - 1 = 255 = $FF
    byte c = -128      ; two's complement byte: 256 - 128 = 128 = $80
    byte d
    d = 0 - 5          ; runtime subtraction, same result: 251

    result1 = a
    result2 = b
    result3 = c
    result4 = d
end
