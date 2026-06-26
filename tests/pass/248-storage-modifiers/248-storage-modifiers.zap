; Test: #ZP and #BSS storage modifiers
; #ZP  forces a variable into the zero-page segment (even structs/arrays).
; #BSS forces a variable into the BSS segment (overrides auto ZP assignment).
; Modifier comes after the initializer (same rule as #PORT comes after @addr).

struct SPoint
    byte x
    byte y
end

; Forced-ZP variables
byte   zp_byte   = 0  #ZP
word   zp_word   = 0  #ZP
long   zp_long   = 0  #ZP
SPoint zp_struct      #ZP
byte   zp_arr[4]      #ZP

; Forced-BSS variable (byte scalar that would otherwise go to ZP)
byte   bss_byte  = 0  #BSS

word result @$0200 = 0

proc check(byte cond)
    if cond != 0
        result += 1
    end
end

proc main()
    ; #ZP byte
    zp_byte = $AB
    check(zp_byte == $AB)               ; [1]

    ; #ZP word
    zp_word = $1234
    check(zp_word == $1234)             ; [2]

    ; #ZP long
    zp_long = $12345678
    check(zp_long == $12345678)         ; [3]

    ; #ZP struct — field access works normally
    zp_struct.x = 10
    zp_struct.y = 20
    check(zp_struct.x == 10)            ; [4]
    check(zp_struct.y == 20)            ; [5]

    ; #ZP array — indexed access works normally
    zp_arr[0] = 1
    zp_arr[1] = 2
    zp_arr[2] = 3
    zp_arr[3] = 4
    check(zp_arr[0] == 1)              ; [6]
    check(zp_arr[3] == 4)              ; [7]

    ; #BSS byte — works exactly like a normal variable
    bss_byte = $CD
    check(bss_byte == $CD)             ; [8]
end
