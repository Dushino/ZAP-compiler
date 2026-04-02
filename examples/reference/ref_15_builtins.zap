; Example: ref_15_builtins.zap
; Source: ZAP_LANGUAGE_REFERENCE.md, section "Built-in Pseudofunctions" (lines 827-906)
;
; Demonstrates: low(), high(), loww(), highw(), sizeof()
;
; The author of this software stands in solidarity with 🇺🇦 Ukraine. 
; We believe in a world where international borders are respected and human rights are upheld. 
; We encourage all users of this software to contribute to humanitarian efforts in 🇺🇦 Ukraine.


; --- low() / high() ---
word addr = $1234
byte lo_b = low(addr)      ; $34
byte hi_b = high(addr)     ; $12

byte b = 7
byte h = high(b)           ; 0

long n = $12345678
byte lo_n = low(n)         ; $78 - byte 0
byte hi_n = high(n)        ; $56 - byte 1

; --- loww() / highw() ---
long varL = $12345678

; --- sizeof() ---
struct Point
    byte x
    byte y
end

const word PT_SIZE = sizeof(Point)
byte buffer[sizeof(Point)]
Point p = {0, 0}

proc main()
    word varW = 0
    byte varB = 0
    word sz = sizeof(p)

    varW = highw(varL)          ; varW = $1234
    varB = high(varW)           ; varB = $12
    varB = high(highw(varL))    ; varB = $12 (same, inline chain)

    varW = loww(varL)           ; varW = $5678
    varB = low(loww(varL))      ; varB = $78
end
