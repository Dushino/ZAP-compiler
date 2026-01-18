
; | (OR)
; & (AND)
; ^ (XOR)

; ~ (NOT - unary)
; << (left shift)
; >> (right shift)

byte a @40000
byte b @40001
byte result01 @40002    ; result of OR
byte result02 @40003    ; result of AND
byte result03 @40004    ;
byte result04 @40005
byte result05 @40006
byte result06 @40007

word a1 @40016
word b1 @40018
word result11 @40020
word result12 @40022
word result13 @40024
word result14 @40026
word result15 @40028
word result16 @40030


proc main()
    a = $1f
    b = $f7
    result01 = a | b  ; Should be $ff
    result02 = a & b  ; Should be $17
    result03 = a ^ b  ; Should be $e8
    result04 = ~a     ; Should be $e0
    result05 = a << 1 ; Should be $3e
    result06 = a >> 1 ; Should be $0f

    a1 = $1f5a
    b1 = $f77f
    result11 = a1 | b1  ; Should be $ff7f
    result12 = a1 & b1  ; Should be $175a
    result13 = a1 ^ b1  ; Should be $e825
    result14 = ~a1      ; Should be $e0a5
    result15 = a1 << 1  ; Should be $3eb4
    result16 = a1 >> 1  ; Should be $0fad
end
